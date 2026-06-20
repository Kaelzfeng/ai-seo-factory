"""lib/preview.py · 本地预览（无 WordPress）—— 现在是【主题驱动】

两个对外函数（签名钉死，勿改；run.py / render_samples.py 都依赖）：
    render_html(page, content, site, all_pages) -> str
    write_index(pages, outdir) -> str

职责划分（"几个模板、以后可拓展"）：
- 本模块只管【逻辑】：站内链接改写、JSON-LD 注入、质检横幅、导航/面包屑/分组数据、写文件；
  它构造一份【与主题无关的 ctx 字典】，交给【当前主题】渲染成完整 HTML。
- 表现交给 lib/themes/<name>.py（见 lib/themes/_base.py 契约）。
- 用哪套主题：行业 config 里写 `theme: <name>`，缺省走 lib.themes.DEFAULT。

兼容旧行为：站内链接改写【只】在 render_html 里发生；schema 经 page["_industry"] 传入；
质检未过的页面渲染醒目横幅而不是抛异常；schema 模块缺失时不报错。
"""
import os
import re
import datetime

from lib import themes
from lib.themes._base import esc as _esc


# ---------------------------------------------------------------------------
# 防御性懒导入 lib.schema（并行构建时可能尚不存在）
# ---------------------------------------------------------------------------
def _jsonld_for(page, content, site, industry):
    """调用 lib.schema.jsonld_for；模块不可用时返回空字符串（不报错）。"""
    try:
        from lib import schema as _schema
        return _schema.jsonld_for(page, content, site, industry) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _norm_url(u: str) -> str:
    """规整 URL 比较：去首尾空白 + 去末尾斜杠（容忍 trailing slash 差异）。"""
    if not u:
        return ""
    return str(u).strip().rstrip("/")


def _today() -> str:
    return datetime.date.today().isoformat()


def _short(title: str, n: int = 24) -> str:
    """导航短标签兜底：优先冒号前一段，否则截断。"""
    t = (title or "").strip()
    if ":" in t:
        t = t.split(":", 1)[0].strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# 类型展示顺序 / 标签（pillar 优先）
_TYPE_ORDER = ["pillar", "comparison", "application", "guide", "faq", "product"]
_TYPE_LABEL = {
    "pillar": "Pillar", "comparison": "Comparison", "application": "Application",
    "guide": "Guide", "faq": "FAQ", "product": "Product",
}


def _type_label(t: str) -> str:
    return _TYPE_LABEL.get(t, (t or "").title() or "Page")


# ---------------------------------------------------------------------------
# 站内链接改写（render_html 独占）
# ---------------------------------------------------------------------------
def _build_url_to_slug(all_pages) -> dict:
    mapping = {}
    for p in all_pages or []:
        url, slug = p.get("url"), p.get("slug")
        if url and slug:
            mapping[_norm_url(url)] = slug
    return mapping


_HREF_RE = re.compile(r'(<a\b[^>]*?\bhref\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE | re.DOTALL)


def _rewrite_internal_links(body_html: str, url_to_slug: dict) -> str:
    """把指向已知站内页 url 的 <a href> 改写成 ./<slug>.html；外链不变。"""
    if not body_html or not url_to_slug:
        return body_html or ""

    def _sub(m):
        prefix, quote, href = m.group(1), m.group(2), m.group(3)
        slug = url_to_slug.get(_norm_url(href))
        return f'{prefix}{quote}./{slug}.html{quote}' if slug else m.group(0)

    return _HREF_RE.sub(_sub, body_html)


# ---------------------------------------------------------------------------
# ctx 构造助手
# ---------------------------------------------------------------------------
def _industry_of(page) -> dict:
    return page.get("_industry") or {}


def _org_name(page, site) -> str:
    ind = _industry_of(page)
    return (ind.get("org_name") or ind.get("name")
            or _norm_url(site).split("//")[-1] or "Site")


def _theme_for(industry: dict):
    """从行业 config 解析当前主题模块（缺省 DEFAULT，失败回退）。"""
    return themes.get_theme((industry or {}).get("theme"))


def _ordered_pages(all_pages):
    """pillar 优先，其余保持原序。"""
    return sorted(all_pages or [], key=lambda p: 0 if p.get("type") == "pillar" else 1)


def _nav_items(all_pages, current_slug):
    items = []
    for p in _ordered_pages(all_pages):
        slug = p.get("slug")
        if not slug:
            continue
        label = p.get("nav_label") or _short(p.get("title") or slug)
        items.append({"label": label, "href": f"./{slug}.html",
                      "active": slug == current_slug})
    return items


def _pillar_slug(all_pages):
    for p in all_pages or []:
        if p.get("type") == "pillar" and p.get("slug"):
            return p["slug"]
    return None


def _crumbs(page, all_pages, site):
    ind = _industry_of(page)
    title = page.get("title") or ""
    crumbs = [{"label": "Home", "href": "./index.html"}]
    if page.get("type") == "pillar":
        crumbs.append({"label": title, "href": None})
        return crumbs
    category = ind.get("default_category") or "Guides"
    ps = _pillar_slug(all_pages)
    crumbs.append({"label": category,
                   "href": f"./{ps}.html" if ps else None})
    crumbs.append({"label": title, "href": None})
    return crumbs


def _warn_html(quality: dict) -> str:
    """质检未过的横幅（内联样式，主题无关，任何主题下都能看清）。"""
    if not quality or quality.get("passed") is not False:
        return ""
    score = quality.get("score")
    issues = quality.get("issues") or []
    li = "".join(f"<li>{_esc(x)}</li>" for x in issues)
    return (
        '<div role="alert" style="margin:18px 0;padding:14px 16px;'
        'border:1px solid #e0a3a0;background:#fcebea;color:#a3271d;'
        'border-radius:10px;font-family:ui-monospace,Menlo,Consolas,monospace;'
        'font-size:13px;line-height:1.55;">'
        f'<strong style="display:block;margin-bottom:6px;font-size:14px;">'
        f'&#9888; Below quality threshold (score {_esc(score)}) '
        '&mdash; preview only, would NOT be published</strong>'
        + (f'<ul style="margin:6px 0 0;padding-left:18px;">{li}</ul>' if li else "")
        + '</div>'
    )


# ---------------------------------------------------------------------------
# render_html — 单页（委托主题）
# ---------------------------------------------------------------------------
def render_html(page: dict, content: dict, site: str, all_pages: list) -> str:
    page = page or {}
    content = content or {}
    all_pages = all_pages or []

    title = content.get("title") or page.get("title") or ""
    meta_desc = content.get("meta_description") or ""
    body = content.get("html") or ""

    # 站内链接改写（仅此一处）
    body = _rewrite_internal_links(body, _build_url_to_slug(all_pages))
    body_has_h1 = bool(re.search(r"(?is)<h1[\s>]", body))

    industry = _industry_of(page)
    ptype = page.get("type") or ""

    ctx = {
        "lang": "en",
        "site": site,
        "org": _org_name(page, site),
        "title": title,
        "meta_desc": meta_desc,
        "body_html": body,
        "body_has_h1": body_has_h1,
        "ptype": ptype,
        "type_label": _type_label(ptype),
        "nav": _nav_items(all_pages, page.get("slug")),
        "crumbs": _crumbs(page, all_pages, site),
        "chips": list(page.get("hero_chips") or []),
        "jsonld": _jsonld_for(page, content, site, industry),
        "warn_html": _warn_html(page.get("_quality") or {}),
        "updated": _today(),
        "year": datetime.date.today().year,
        "robots": "noindex",
    }
    return _theme_for(industry).render_page(ctx)


# ---------------------------------------------------------------------------
# write_index — 站点首页（委托主题）
# ---------------------------------------------------------------------------
def _index_site_name(pages) -> str:
    for p in pages or []:
        ind = _industry_of(p)
        nm = ind.get("org_name") or ind.get("name")
        if nm:
            return nm
    return "Content Preview"


def _page_passed(p) -> bool:
    q = p.get("_quality")
    return True if not q else bool(q.get("passed"))


def _index_groups(pages):
    by_type = {}
    for p in pages:
        by_type.setdefault(p.get("type") or "other", []).append(p)
    ordered = [t for t in _TYPE_ORDER if t in by_type]
    ordered += sorted(t for t in by_type if t not in _TYPE_ORDER)

    groups = []
    for t in ordered:
        items = []
        for p in by_type[t]:
            slug = p.get("slug") or ""
            content = p.get("_content") or {}
            passed = _page_passed(p)
            items.append({
                "title": p.get("title") or slug,
                "href": (f"./{slug}.html" if passed else None),
                "teaser": content.get("meta_description") or "",
                "type_label": _type_label(t),
                "passed": passed,
            })
        groups.append({"type": t, "label": _type_label(t), "items": items})
    return groups


def _index_theme(pages):
    for p in pages or []:
        ind = _industry_of(p)
        if ind:
            return _theme_for(ind)
    return themes.get_theme(None)


def write_index(pages: list, outdir: str) -> str:
    pages = pages or []
    os.makedirs(outdir, exist_ok=True)

    total = len(pages)
    n_pass = sum(1 for p in pages if _page_passed(p))
    n_skip = total - n_pass
    sub = f"{total} page{'s' if total != 1 else ''}"
    if n_skip:
        sub += f" · {n_pass} live · {n_skip} below threshold"

    # 任取一页的 site 兜底（首页本身不强依赖 site）
    any_site = next((p.get("url") for p in pages if p.get("url")), "") or ""
    ctx = {
        "lang": "en",
        "site": _norm_url(any_site).rsplit("/", 1)[0] if any_site else "",
        "org": _index_site_name(pages),
        "site_name": _index_site_name(pages),
        "sub": f"{sub} · generated {_today()}",
        "year": datetime.date.today().year,
        "robots": "noindex",
        "nav": _nav_items(pages, None),
        "stats": {"total": total, "n_pass": n_pass, "n_skip": n_skip},
        "groups": _index_groups(pages),
    }
    doc = _index_theme(pages).render_index(ctx)

    path = os.path.join(outdir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return os.path.abspath(path)
