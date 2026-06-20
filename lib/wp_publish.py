"""WordPress REST 适配器（硬化版）。

按 BUILD SPEC §7 实现：
- 单一 requests.Session + urllib3 Retry（连接级容错）
- dry_run 开关：所有网络方法短路成确定性 stub，绝不发 HTTP
- 发文时把 JSON-LD 注入正文（schema injection）
- SEO meta 用独立请求写入（Yoast / RankMath / Rank Math API），并回读校验，
  失败时 fallback 到 excerpt
- 分类 / 标签都做 get-or-create（幂等）
- 错误信息可操作：401 提示 Apache 剥离 Authorization 头的修法，链接异常提示
  开启 pretty permalinks
"""
import io
import os
import re
import time

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth

try:  # urllib3 的 Retry 在新旧版本路径不同，做个兼容
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - 极少触发
    from requests.packages.urllib3.util.retry import Retry  # type: ignore


# ---------------------------------------------------------------------------
# 模块级常量 / 异常（INTERFACES 中已 pin 死）
# ---------------------------------------------------------------------------

# HTTP 状态码 → 人类可读的常见根因（用于错误信息拼装）
WP_STATUS_CAUSE = {
    400: ("请求被拒（400）。常见原因：meta 字段未通过 register_post_meta 注册、"
          "term_exists（分类/标签已存在）、或 slug 非法。"),
    401: ("未认证（401）。最常见原因：Apache/Nginx 把 Authorization 头剥掉了，"
          "Application Password 永远到不了 WordPress。修法见 .htaccess 提示。"),
    403: ("被禁止（403）。可能是 WAF / 安全插件 / Cloudflare 拦了 REST，"
          "或当前用户权限不足。注意：返回体若是 HTML 而非 JSON，基本就是 WAF。"),
    404: ("未找到（404）。REST 路由不存在或被禁用，确认 /wp-json/ 可访问、"
          "且固定链接已刷新。"),
    409: "冲突（409）。资源已存在或状态冲突。",
    413: ("请求体过大（413）。服务器 upload_max_filesize / post_max_size / "
          "client_max_body_size 太小，调大或先把图片压缩降采样。"),
    429: "请求过于频繁（429）。已触发限流，按 Retry-After 退避后重试。",
    500: "服务器内部错误（500）。多为插件/主题报错，查 WP 错误日志。",
    502: "网关错误（502）。上游 PHP/服务器临时不可用，稍后重试。",
    503: "服务不可用（503）。站点维护或过载，稍后重试。",
    504: "网关超时（504）。上游处理超时，稍后重试。",
}

# 给 Yoast / RankMath 在 REST 暴露 meta 字段用的 mu-plugin 片段（写进错误提示/文档）
MU_PLUGIN_SNIPPET = r"""<?php
/*
 * Plugin Name: SEO Meta REST Bridge (mu-plugin)
 * 放到 wp-content/mu-plugins/seo-meta-rest.php
 * 作用：把 Yoast / Rank Math 的 meta key 注册到 REST，使外部可写 meta description。
 */
add_action('init', function () {
    $keys = [
        '_yoast_wpseo_metadesc',   // Yoast meta description
        '_yoast_wpseo_title',      // Yoast SEO title
        '_yoast_wpseo_focuskw',    // Yoast focus keyword
        'rank_math_description',   // Rank Math description
        'rank_math_title',         // Rank Math title
        'rank_math_focus_keyword', // Rank Math focus keyword
    ];
    foreach ($keys as $key) {
        register_post_meta('post', $key, [
            'type'          => 'string',
            'single'        => true,
            'show_in_rest'  => true,
            'auth_callback' => function () { return current_user_can('edit_posts'); },
        ]);
    }
});
"""

# 当 401 时给出的 Apache .htaccess 修复提示（Authorization 头被剥）
_HTACCESS_AUTH_FIX = (
    "401 通常不是密码错，而是服务器把 HTTP Authorization 头吃掉了，"
    "Application Password 根本没送到 WordPress。\n"
    "在 .htaccess（WordPress 根目录）顶部加上其一：\n"
    "  # 方案 A：SetEnvIf\n"
    "  SetEnvIf Authorization \"(.*)\" HTTP_AUTHORIZATION=$1\n"
    "  # 方案 B：RewriteRule（放在 RewriteEngine On 之后）\n"
    "  RewriteCond %{HTTP:Authorization} ^(.*)\n"
    "  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%1]\n"
    "Nginx 用户：确认 fastcgi_param HTTP_AUTHORIZATION 已透传。"
)


class WordPressError(Exception):
    """带结构化字段的 WP 错误。

    .code   WP 返回的 error code 或合成 code
    .status HTTP 状态码（int 或 None）
    .hint   人类可读、可操作的修复建议
    """

    def __init__(self, message, code=None, status=None, hint=""):
        super().__init__(message)
        self.code = code
        self.status = status
        self.hint = hint

    def __str__(self):
        base = super().__str__()
        parts = [base]
        if self.code:
            parts.append(f"[code={self.code}]")
        if self.status is not None:
            parts.append(f"[status={self.status}]")
        if self.hint:
            parts.append(f"\n→ 提示：{self.hint}")
        return " ".join(parts[:3]) + (parts[3] if len(parts) > 3 else "")


# 可重试的连接级异常（与 should_retry 配合）
_CONN_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
# 可重试的 HTTP 状态码（仅幂等/安全场景使用）
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# 允许上传的图片 MIME → 扩展名
_ALLOWED_IMAGE_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# ---------------------------------------------------------------------------
# 本地的轻量 retry（当 lib.retry 尚未就位时的兜底；优先用共享实现）
# ---------------------------------------------------------------------------
try:  # 与 lib/retry.py 的 call_with_retry 对齐（参数同名）
    from lib.retry import call_with_retry as _shared_call_with_retry
except Exception:  # pragma: no cover - 并行构建期 lib.retry 可能还没生成
    _shared_call_with_retry = None


def _call_with_retry(fn, *, attempts=4, base_delay=1.0, max_delay=30.0,
                     jitter=0.25, retry_on=_CONN_ERRORS, should_retry=None,
                     on_retry=None):
    """运行 fn()，遇到可重试异常时指数退避 + 抖动重试。

    优先委托给共享的 lib.retry.call_with_retry；没有时用本地等价实现。
    """
    if _shared_call_with_retry is not None:
        return _shared_call_with_retry(
            fn, attempts=attempts, base_delay=base_delay, max_delay=max_delay,
            jitter=jitter, retry_on=retry_on, should_retry=should_retry,
            on_retry=on_retry,
        )
    import random
    last = None
    for n in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 由 should_retry/retry_on 决定
            last = exc
            ok = should_retry(exc) if should_retry else isinstance(exc, retry_on)
            if not ok or n >= attempts:
                raise
            sleep = min(max_delay, base_delay * (2 ** (n - 1)))
            sleep += sleep * jitter * (random.random() * 2 - 1)
            sleep = max(0.0, sleep)
            # 若异常携带 Retry-After，优先尊重它
            ra = getattr(exc, "retry_after", None)
            if ra is not None:
                sleep = max(sleep, float(ra))
            if on_retry:
                on_retry(n, exc, sleep)
            time.sleep(sleep)
    raise last  # pragma: no cover


# ---------------------------------------------------------------------------
# WordPress 适配器
# ---------------------------------------------------------------------------
class WordPress:
    def __init__(self, site=None, user=None, app_password=None, dry_run: bool = False,
                 api_base=None):
        """dry_run=True 时所有网络方法变成 no-op，返回可信的 stub，不发任何 HTTP。

        site/user/app_password 为 None 时从环境变量 WP_SITE / WP_USER /
        WP_APP_PASSWORD 读取。非 dry_run 时强制 https://（http:// 抛 ValueError）。
        构造一个带 urllib3 Retry 适配器的 requests.Session 做连接级容错。
        __init__ 不做 probe（probe 显式走 verify_auth）。
        """
        self.dry_run = dry_run

        raw_site = site or os.getenv("WP_SITE") or ""
        self.site = raw_site.rstrip("/")  # 公开站点 URL：仅用于拼链接/JSON-LD，不传凭据
        # 传输端点：REST 请求(含 Application Password)实际发往这里。默认=site；
        # 可设 WP_API_BASE 指到 SSH 隧道的本机回环(http://127.0.0.1:<port>),
        # 让凭据只走 loopback + SSH 加密通道,公网段永不见明文。
        raw_api = api_base or os.getenv("WP_API_BASE") or self.site
        self.api_base = raw_api.rstrip("/")
        if not self.dry_run:
            if not self.site:
                raise ValueError("缺少 WP_SITE（且非 dry_run）。请设置环境变量或显式传入。")
            # —— 传输安全 ——
            # Application Password 走 HTTP Basic Auth,明文可被截获。强制凭据端点(api_base)
            # 用 https；唯一例外:http 且目标是**本机回环**(localhost/127.0.0.1/::1),
            # 这是给「经 SSH 隧道发布」用的——明文只在回环内,公网段由 SSH 负责加密。
            from urllib.parse import urlparse
            allow_http = os.getenv("WP_ALLOW_HTTP", "").strip().lower() in ("1", "true", "yes")
            api_host = (urlparse(self.api_base).hostname or "").lower()
            api_loopback = api_host in ("localhost", "127.0.0.1", "::1")
            if self.api_base.startswith("http://"):
                if not (allow_http and api_loopback):
                    raise ValueError(
                        "拒绝把 Application Password 明文发往 http://(且非回环)。"
                        "请用 https:// 端点;或经 SSH 隧道把 WP_API_BASE 指到 "
                        "http://127.0.0.1:<port> 并设 WP_ALLOW_HTTP=1(明文仅走回环)。"
                    )
            elif not self.api_base.startswith("https://"):
                raise ValueError(f"WP_API_BASE 必须是 http(s):// 开头，得到：{self.api_base!r}")
        else:
            # dry_run 下没站点也无所谓，给个占位以拼出 stub 链接
            if not self.site:
                self.site = "https://demo.local"
            self.api_base = self.site

        self.api = f"{self.api_base}/wp-json/wp/v2"

        self._user = user or os.getenv("WP_USER")
        self._app_password = app_password or os.getenv("WP_APP_PASSWORD")
        if not self.dry_run and (not self._user or not self._app_password):
            raise ValueError(
                "缺少 WP_USER / WP_APP_PASSWORD（且非 dry_run）。"
                "请在 .env 配置，或显式传入。"
            )
        self.auth = (
            HTTPBasicAuth(self._user, self._app_password)
            if (self._user and self._app_password)
            else None
        )

        # 单一 Session + 连接级 Retry 适配器
        self.session = requests.Session()
        if not self.dry_run:
            retry = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

        self._plugin_cache = None  # detect_seo_plugin 的缓存

    # ------------------------------------------------------------------
    # 内部 HTTP 工具
    # ------------------------------------------------------------------
    def _request(self, method, url, *, retry=False, **kwargs):
        """统一发请求；retry=True 时对连接错误/可重试状态码做退避重试。

        非 dry_run 才会被调用（dry_run 路径在各方法里提前短路）。
        """
        kwargs.setdefault("timeout", 60)
        if self.auth is not None:
            kwargs.setdefault("auth", self.auth)

        def _do():
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code in _RETRYABLE_STATUS:
                # 让 _call_with_retry 看到状态码以决定是否重试
                exc = WordPressError(
                    f"{method} {url} 返回可重试状态 {resp.status_code}",
                    status=resp.status_code,
                )
                ra = resp.headers.get("Retry-After")
                if ra:
                    try:
                        exc.retry_after = float(ra)
                    except ValueError:
                        exc.retry_after = None
                raise exc
            return resp

        if not retry:
            return self.session.request(method, url, **kwargs)

        def _should_retry(exc):
            if isinstance(exc, _CONN_ERRORS):
                return True
            if isinstance(exc, WordPressError):
                return exc.status in _RETRYABLE_STATUS
            return False

        return _call_with_retry(_do, should_retry=_should_retry)

    @staticmethod
    def _parse_error(resp):
        """从响应里抽出 (code, status, message, is_html)。"""
        status = resp.status_code
        text = resp.text or ""
        ctype = resp.headers.get("Content-Type", "")
        is_html = ("application/json" not in ctype) and (
            "<html" in text.lower() or "<!doctype" in text.lower()
        )
        code = None
        message = text[:300]
        if not is_html:
            try:
                data = resp.json()
                if isinstance(data, dict):
                    code = data.get("code")
                    message = data.get("message", message)
                    status = (data.get("data") or {}).get("status", status)
            except ValueError:
                pass
        return code, status, message, is_html

    def _raise_for_status(self, resp, *, context=""):
        """把 4xx/5xx 翻译成带可操作 hint 的 WordPressError。"""
        if resp.status_code < 400:
            return
        code, status, message, is_html = self._parse_error(resp)
        hint = WP_STATUS_CAUSE.get(status, "")
        if status == 401:
            hint = _HTACCESS_AUTH_FIX
        elif status == 403 and is_html:
            hint = "返回体是 HTML（非 JSON），几乎可以确定是 WAF/安全插件/Cloudflare 拦截了 REST 请求。"
        elif status == 400 and code in ("rest_post_invalid_id", "rest_invalid_param"):
            hint = WP_STATUS_CAUSE[400]
        prefix = f"{context}：" if context else ""
        raise WordPressError(
            f"{prefix}{message}",
            code=code or f"http_{status}",
            status=status,
            hint=hint,
        )

    # ------------------------------------------------------------------
    # preflight
    # ------------------------------------------------------------------
    def verify_auth(self) -> dict:
        """GET /users/me?context=edit，确认认证可用。

        返回 {"ok": bool, "user": str|None, "warnings": list[str]}。
        401 抛出点名 Apache Authorization 头修法的 WordPressError。dry_run 直接 ok。
        """
        if self.dry_run:
            return {"ok": True, "user": "(dry_run)", "warnings": ["dry_run"]}

        url = f"{self.api}/users/me"
        resp = self._request("GET", url, params={"context": "edit"}, retry=True)
        if resp.status_code == 401:
            raise WordPressError(
                "WordPress 拒绝认证（401）。",
                code="rest_not_logged_in",
                status=401,
                hint=_HTACCESS_AUTH_FIX,
            )
        self._raise_for_status(resp, context="verify_auth")
        data = resp.json()
        warnings = []
        user = data.get("name") or data.get("slug")
        caps = data.get("capabilities") or {}
        if caps and not (caps.get("publish_posts") or caps.get("edit_posts")):
            warnings.append("当前用户疑似无发文权限（缺 publish_posts/edit_posts）。")
        return {"ok": True, "user": user, "warnings": warnings}

    def detect_seo_plugin(self) -> dict:
        """GET {site}/wp-json，扫描 routes 判断 SEO 插件。

        返回 {"yoast": bool, "rankmath": bool, "rankmath_api": bool}，实例上缓存。
        rankmath_api 为 True 当且仅当存在 /rank-math-api/v1/update-meta 路由。
        """
        if self._plugin_cache is not None:
            return self._plugin_cache
        if self.dry_run:
            self._plugin_cache = {"yoast": False, "rankmath": False, "rankmath_api": False}
            return self._plugin_cache

        result = {"yoast": False, "rankmath": False, "rankmath_api": False}
        try:
            resp = self._request("GET", f"{self.api_base}/wp-json", retry=True)
            if resp.status_code < 400:
                data = resp.json()
                routes = data.get("routes") or {}
                route_keys = " ".join(routes.keys()) if isinstance(routes, dict) else ""
                namespaces = data.get("namespaces") or []
                blob = route_keys + " " + " ".join(namespaces)
                low = blob.lower()
                if "/rank-math-api/v1/update-meta" in blob:
                    result["rankmath_api"] = True
                if "rank-math" in low or "rankmath" in low:
                    result["rankmath"] = True
                if "yoast" in low:
                    result["yoast"] = True
        except (requests.RequestException, ValueError, WordPressError):
            # 探测失败不致命：当作未知插件，create_post 会回读校验后给 warning
            pass
        self._plugin_cache = result
        return result

    # ------------------------------------------------------------------
    # media URL
    # ------------------------------------------------------------------
    def get_media_url(self, media_id):
        """GET /media/{id} → source_url（已上传媒体的真实公开 URL）。

        供 run.py 在发布模式下给 JSON-LD(schema) 注入真实配图地址用。
        拿不到 / dry_run / media_id 为空时返回 None（schema image 省略，不致命）。
        """
        if self.dry_run or not media_id:
            return None
        try:
            resp = self._request("GET", f"{self.api}/media/{media_id}", retry=True)
            if resp.status_code < 400:
                return (resp.json() or {}).get("source_url")
        except (requests.RequestException, ValueError, WordPressError):
            pass
        return None

    # ------------------------------------------------------------------
    # taxonomy（幂等 get-or-create）
    # ------------------------------------------------------------------
    def _slugify(self, name: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return s or name.lower()

    def _get_or_create_term(self, taxonomy: str, name: str) -> int:
        """taxonomy ∈ {'categories','tags'}。按 slug 再按 exact name 命中，否则创建。"""
        if self.dry_run:
            return -1

        endpoint = f"{self.api}/{taxonomy}"
        slug = self._slugify(name)
        # 先按 slug 精确查
        resp = self._request("GET", endpoint,
                             params={"slug": slug, "per_page": 100}, retry=True)
        if resp.status_code < 400:
            for term in resp.json():
                if term.get("slug") == slug or \
                        term.get("name", "").lower() == name.lower():
                    return term["id"]
        # 退一步按 name 搜
        resp = self._request("GET", endpoint,
                             params={"search": name, "per_page": 100}, retry=True)
        if resp.status_code < 400:
            for term in resp.json():
                if term.get("name", "").lower() == name.lower():
                    return term["id"]
        # 创建
        resp = self._request("POST", endpoint, json={"name": name})
        if resp.status_code < 400:
            return resp.json()["id"]
        # term_exists：从 data.term_id 取回
        code, status, message, _ = self._parse_error(resp)
        if code == "term_exists":
            try:
                term_id = (resp.json().get("data") or {}).get("term_id")
                if term_id:
                    return int(term_id)
            except (ValueError, TypeError, AttributeError):
                pass
            # data 里没带 id 就再查一次
            resp2 = self._request("GET", endpoint, params={"slug": slug, "per_page": 100})
            if resp2.status_code < 400 and resp2.json():
                return resp2.json()[0]["id"]
        self._raise_for_status(resp, context=f"创建 {taxonomy} '{name}'")
        raise WordPressError(f"无法 get-or-create {taxonomy} '{name}'", status=status)

    def get_or_create_category(self, name: str) -> int:
        return self._get_or_create_term("categories", name)

    def get_or_create_tag(self, name: str) -> int:
        return self._get_or_create_term("tags", name)

    # ------------------------------------------------------------------
    # media
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize_filename(filename: str, content_type: str) -> str:
        """ASCII 化文件名，并把扩展名强制对齐 content_type。"""
        ext = _ALLOWED_IMAGE_MIME.get(content_type, ".jpg")
        base = os.path.splitext(filename or "image")[0]
        base = base.encode("ascii", "ignore").decode("ascii")
        base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._")
        if not base:
            base = "image"
        return base + ext

    def upload_image(self, image_bytes: bytes, filename: str,
                     content_type: str = "image/jpeg") -> int:
        """上传图片，返回 media id。

        ASCII 化文件名 + 扩展名对齐 content_type；校验 MIME ∈ {jpeg,png,webp}。
        上传非幂等：不做盲重试，只对连接级/响应前错误重试。413 给出可操作错误。
        dry_run 返回 0。
        """
        if content_type not in _ALLOWED_IMAGE_MIME:
            raise WordPressError(
                f"不支持的图片类型 {content_type!r}，仅允许 "
                f"{sorted(_ALLOWED_IMAGE_MIME)}。",
                code="unsupported_media_type",
                status=415,
                hint="先把图片转成 JPEG/PNG/WebP。",
            )
        if self.dry_run:
            return 0

        safe_name = self._sanitize_filename(filename, content_type)
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Type": content_type,
        }
        url = f"{self.api}/media"

        # 仅对连接级错误重试（上传非幂等，不能因状态码盲重试以免重复上传）
        def _do():
            return self.session.post(
                url, data=io.BytesIO(image_bytes), headers=headers,
                auth=self.auth, timeout=120,
            )

        resp = _call_with_retry(
            _do,
            should_retry=lambda e: isinstance(e, _CONN_ERRORS),
        )
        if resp.status_code == 413:
            raise WordPressError(
                "图片上传被拒（413 请求体过大）。",
                code="rest_upload_too_large",
                status=413,
                hint="调大服务器 upload_max_filesize / post_max_size / "
                     "client_max_body_size，或先把图片降采样/压缩后再传。",
            )
        self._raise_for_status(resp, context="upload_image")
        return resp.json()["id"]

    def set_media_meta(self, media_id: int, alt_text: str = "", title: str = "",
                       caption: str = "") -> None:
        """可选：PATCH/POST /media/{id} 设置 alt_text/title/caption。dry_run no-op。"""
        if self.dry_run:
            return
        payload = {}
        if alt_text:
            payload["alt_text"] = alt_text
        if title:
            payload["title"] = title
        if caption:
            payload["caption"] = caption
        if not payload:
            return
        resp = self._request("POST", f"{self.api}/media/{media_id}", json=payload)
        self._raise_for_status(resp, context="set_media_meta")

    # ------------------------------------------------------------------
    # post
    # ------------------------------------------------------------------
    def create_post(self, title: str, html: str, slug: str, meta_description: str = "",
                    category_ids=None, tag_ids=None, featured_media=None,
                    json_ld: str = "", status: str = "publish") -> dict:
        """创建文章。

        若提供 json_ld，则在发送前追加到 html 末尾（schema 注入正文）。
        create payload 不携带 meta key（meta 走独立请求）。
        返回 {"id","link","slug","warnings"}。dry_run 返回 stub。
        流程：(1) POST 创建（无 meta） (2) detect_seo_plugin
              (3) apply_seo_meta 独立请求 (4) ?context=edit 回读校验 meta
              (5) 校验 link 是否 pretty permalink；否则加 warning。
        发文不做盲重试（避免重复发布）。
        """
        warnings = []

        if self.dry_run:
            return {
                "id": 0,
                "link": f"{self.site}/{slug}/",
                "slug": slug,
                "warnings": ["dry_run"],
            }

        # JSON-LD 注入正文（发布与预览两端都要带 schema）
        content_html = html
        if json_ld:
            content_html = f"{html}\n\n{json_ld}\n"

        payload = {
            "title": title,
            "content": content_html,
            "slug": slug,
            "status": status,
            "excerpt": meta_description,  # excerpt 作为通用 fallback，始终写入
        }
        if category_ids:
            payload["categories"] = category_ids
        if tag_ids:
            payload["tags"] = tag_ids
        if featured_media:
            payload["featured_media"] = featured_media

        # (1) 创建（NO meta，且不盲重试）
        resp = self._request("POST", f"{self.api}/posts", json=payload, retry=False)
        self._raise_for_status(resp, context="create_post")
        data = resp.json()
        post_id = data["id"]
        real_slug = data.get("slug", slug)
        link = data.get("link", "")

        # (2)(3) 写 SEO meta（独立请求，按插件分派）
        meta_result = self.apply_seo_meta(
            post_id, meta_description, title=title,
            focus_keyword="",
        )
        warnings.extend(meta_result.get("warnings", []))

        # (4) 回读校验 meta 是否落库
        if meta_description and not meta_result.get("applied"):
            applied = self._verify_meta_applied(post_id, meta_description)
            if not applied:
                warnings.append("seo_meta_not_applied")

        # (5) 校验 pretty permalink
        if link and ("?p=" in link or "?page_id=" in link or "/?" in link):
            warnings.append("permalinks_not_pretty")

        return {
            "id": post_id,
            "link": link,
            "slug": real_slug,
            "warnings": warnings,
        }

    def _verify_meta_applied(self, post_id: int, meta_description: str) -> bool:
        """?context=edit 回读，确认 meta description 落到了某个已知 SEO key 或 excerpt。"""
        try:
            resp = self._request("GET", f"{self.api}/posts/{post_id}",
                                 params={"context": "edit"}, retry=True)
            if resp.status_code >= 400:
                return False
            data = resp.json()
            meta = data.get("meta") or {}
            for key in ("_yoast_wpseo_metadesc", "rank_math_description"):
                if str(meta.get(key, "")).strip() == meta_description.strip():
                    return True
            # excerpt 作为通用 fallback 也算落库成功
            excerpt = ((data.get("excerpt") or {}).get("raw")
                       or (data.get("excerpt") or {}).get("rendered") or "")
            if meta_description.strip() and meta_description.strip()[:60] in excerpt:
                return True
        except (requests.RequestException, ValueError, WordPressError):
            return False
        return False

    def apply_seo_meta(self, post_id: int, meta_description: str, title: str = "",
                       focus_keyword: str = "") -> dict:
        """独立请求写 SEO meta，按检测到的插件分派。

        - 有 Rank Math API（/rank-math-api/v1/update-meta）→ 用它
        - 否则用 register_post_meta 暴露的 meta key（仅对已激活插件）
        excerpt 由 create_post 写入，作为通用 fallback。
        返回 {"applied": bool, "via": str, "warnings": list[str]}。
        """
        if self.dry_run:
            return {"applied": True, "via": "dry_run", "warnings": ["dry_run"]}
        if not meta_description and not title and not focus_keyword:
            return {"applied": False, "via": "none", "warnings": []}

        plugins = self.detect_seo_plugin()
        warnings = []

        # 优先：Rank Math API Manager 端点（不依赖 register_post_meta）
        if plugins.get("rankmath_api"):
            url = f"{self.api_base}/wp-json/rank-math-api/v1/update-meta"
            payload = {"objectID": post_id, "objectType": "post"}
            if meta_description:
                payload["rank_math_description"] = meta_description
            if title:
                payload["rank_math_title"] = title
            if focus_keyword:
                payload["rank_math_focus_keyword"] = focus_keyword
            try:
                resp = self._request("POST", url, json=payload, retry=True)
                if resp.status_code < 400:
                    return {"applied": True, "via": "rank-math-api", "warnings": warnings}
                code, _, msg, _ = self._parse_error(resp)
                warnings.append(f"rank_math_api_failed:{code or msg[:60]}")
            except (requests.RequestException, WordPressError) as exc:
                warnings.append(f"rank_math_api_error:{exc}")

        # 退路：通过 wp/v2/posts 的 meta（需 register_post_meta 暴露字段）
        meta = {}
        if plugins.get("yoast") or not (plugins.get("rankmath") or plugins.get("yoast")):
            if meta_description:
                meta["_yoast_wpseo_metadesc"] = meta_description
            if title:
                meta["_yoast_wpseo_title"] = title
            if focus_keyword:
                meta["_yoast_wpseo_focuskw"] = focus_keyword
        if plugins.get("rankmath"):
            if meta_description:
                meta["rank_math_description"] = meta_description
            if title:
                meta["rank_math_title"] = title
            if focus_keyword:
                meta["rank_math_focus_keyword"] = focus_keyword

        if meta:
            resp = self._request("POST", f"{self.api}/posts/{post_id}",
                                 json={"meta": meta}, retry=False)
            if resp.status_code < 400:
                # 回读确认（meta 字段可能没注册，REST 会静默丢弃）
                if self._verify_meta_applied(post_id, meta_description):
                    return {"applied": True, "via": "post-meta", "warnings": warnings}
                warnings.append(
                    "seo_meta_not_applied"
                )
                warnings.append(
                    "meta 字段疑似未通过 register_post_meta 暴露到 REST；"
                    "请安装 mu-plugin（见 MU_PLUGIN_SNIPPET）。excerpt 已作为 fallback 写入。"
                )
                return {"applied": False, "via": "post-meta", "warnings": warnings}
            code, _, msg, _ = self._parse_error(resp)
            warnings.append(f"post_meta_rejected:{code or msg[:60]}")

        # 没插件 / 没法写：excerpt 已是 fallback
        warnings.append(
            "未检测到可写的 SEO 插件 meta 通道；meta description 已写入 excerpt 作为 fallback。"
        )
        return {"applied": False, "via": "excerpt-fallback", "warnings": warnings}
