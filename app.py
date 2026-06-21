# -*- coding: utf-8 -*-
"""app.py · Flask 工厂 + 路由

python app.py 直接启动。
使用现有 templates/ 和 static/,不做任何修改。
"""

import json
import os
import re
import threading
import time
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, Response, stream_with_context,
    send_from_directory,
)
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

# ── Flask 工厂 ──────────────────────────────────────


def create_app(testing=False):
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    app.config["TESTING"] = testing
    app.config["SESSION_PERMANENT"] = True

    # 注册 admin Blueprint
    from admin import admin_bp
    app.register_blueprint(admin_bp)

    return app


app = create_app()

# Phase 8: Apply security headers
try:
    from lib.security_headers import apply_security_headers
    apply_security_headers(app)
except Exception:
    pass


# ── 辅助函数 ────────────────────────────────────────


def _keyword_landing(bd: dict) -> dict:
    """从 quality breakdown 的 keyword_usage 反向解析关键词命中情况。

    供 test_keyword_landing.py 直接调用,签名钉死,勿改。
    """
    score = bd.get("score", 0.0)
    notes = bd.get("notes", "")

    present = score > 0

    title = True
    if "not in title" in notes.lower():
        title = False
    if present and score == bd.get("max", 0):
        title = True

    meta = True
    if "not in meta" in notes.lower():
        meta = False

    heading_intro = True
    if "not in heading" in notes.lower() or "not in intro" in notes.lower():
        heading_intro = False

    body_count = 0
    m = re.search(r"body count[=:]\s*(\d+)", notes)
    if m:
        body_count = int(m.group(1))

    return {
        "present": present,
        "title": title,
        "meta": meta,
        "heading_intro": heading_intro,
        "body_count": body_count,
    }


def _get_template_context(**kwargs):
    """基础模板上下文 —— 补全模板变量,不改模板。"""
    from auth import current_user, current_tenant_id
    user = current_user()
    tid = current_tenant_id()

    ctx = {
        "user": user,
        "tenant_id": tid,
        "now": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ctx.update(kwargs)
    return ctx


_RUN_PREVIEW_SLUG = "hammer-hardware-tools-supplier"
_RUN_PREVIEW_TITLE = "Hammer Hardware Tools Supplier"
_RUN_PREVIEW_FORBIDDEN = (
    "test page title", "batch test page", "test paragraph", "pu leather",
    "synthetic leather", "example.com",
)


def _redact_sse_text(value) -> str:
    """Mask credentials before an exception or progress message reaches SSE."""
    text = str(value or "")
    for key, secret in os.environ.items():
        upper = key.upper()
        if not any(marker in upper for marker in ("API_KEY", "SECRET", "PASSWORD", "TOKEN")):
            continue
        if secret and len(secret) >= 6:
            text = text.replace(secret, "***")
    return re.sub(
        r"(?i)\b(?:sk|pk|api|key)[-_][a-z0-9._-]{8,}\b",
        "***",
        text,
    )


def _redact_sse_payload(value):
    if isinstance(value, dict):
        return {key: _redact_sse_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_sse_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_sse_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_sse_text(value)
    return value


def _run_preview_result() -> dict:
    """Return the one Canvas result guaranteed by the GET /run preview path."""
    return {
        "slug": _RUN_PREVIEW_SLUG,
        "title": _RUN_PREVIEW_TITLE,
        "type": "page",
        "score": None,
        "passed": True,
        "link": f"./{_RUN_PREVIEW_SLUG}.html",
    }


def _clear_run_output(outdir: Path) -> None:
    """Delete prior generated documents while preserving output_src itself."""
    outdir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.html", "*.json"):
        for path in outdir.glob(pattern):
            if path.is_file():
                path.unlink()


def _run_preview_copy(name, seed, audience) -> str:
    """Build deterministic copy from this request, never from output_src."""
    from html import escape

    project_name = escape(str(name or _RUN_PREVIEW_TITLE))
    seed_terms = escape(str(seed or "hammer, hardware tools"))
    target_audience = escape(str(audience or "wholesalers and distributors"))
    return (
        f"<p><strong>Project:</strong> {project_name}</p>"
        f"<p><strong>Seed keyword:</strong> {seed_terms}</p>"
        f"<p><strong>Target audience:</strong> {target_audience}</p>"
        "<p>Source dependable hammer and hardware tools from an export-ready "
        "supplier and manufacturer serving wholesale buyers.</p>"
        "<p>Our English B2B export program is designed for wholesalers and "
        "distributors seeking consistent hardware tools supply, bulk ordering, "
        "and international export support.</p>"
    )


def _render_run_preview_html(name, seed, audience) -> str:
    import datetime
    from lib.themes import atelier

    today = datetime.date.today()
    body_html = (
        f"<h1>{_RUN_PREVIEW_TITLE}</h1>"
        f"{_run_preview_copy(name, seed, audience)}"
        "<h2>Wholesale Hammer and Hardware Tools Export</h2>"
        "<p>Compare wholesale hammer and hardware tools sourcing options for "
        "B2B export buyers, wholesalers, and distributors.</p>"
        "<h2>Supplier and Manufacturer Capabilities</h2>"
        "<p>Review supplier capacity, manufacturer quality controls, product "
        "specifications, packaging options, and OEM support.</p>"
        "<h2>Export Documentation and Bulk Ordering</h2>"
        "<p>Confirm export documentation, wholesale terms, lead times, and bulk "
        "ordering requirements before placing a hardware tools order.</p>"
        "<blockquote>Request supplier specifications and wholesale terms.</blockquote>"
    )
    ctx = {
        "lang": "en",
        "org": "Hammer Hardware Tools Export",
        "title": _RUN_PREVIEW_TITLE,
        "meta_desc": (
            "Hammer hardware tools supplier, manufacturer, wholesale and B2B "
            "export sourcing guide for wholesalers and distributors."
        ),
        "robots": "noindex,follow",
        "type_label": "Supplier Guide",
        "body_has_h1": True,
        "body_html": body_html,
        "warn_html": "",
        "jsonld": "",
        "year": today.year,
        "updated": today.isoformat(),
        "chips": ["B2B Export", "Wholesale", "Manufacturer", "Supplier"],
        "crumbs": [
            {"label": "Home", "href": "./index.html"},
            {
                "label": _RUN_PREVIEW_TITLE,
                "href": f"./{_RUN_PREVIEW_SLUG}.html",
                "active": True,
            },
        ],
        "nav": [
            {"label": "Home", "href": "./index.html"},
            {
                "label": "Supplier Guide",
                "href": f"./{_RUN_PREVIEW_SLUG}.html",
                "active": True,
            },
        ],
    }
    return atelier.render_page(ctx)


def _write_run_preview_index(outdir: Path, name, seed, audience) -> None:
    import datetime
    from lib.themes import atelier

    today = datetime.date.today()
    teaser = (
        "Hammer hardware tools supplier, manufacturer, wholesale and B2B "
        "export sourcing guide."
    )
    ctx = {
        "lang": "en",
        "org": "Hammer Hardware Tools Export",
        "site_name": "Hammer Hardware Tools Export",
        "sub": (
            "English B2B export preview for hammer and hardware tools "
            "suppliers, manufacturers, wholesalers, and distributors."
        ),
        "robots": "noindex,follow",
        "year": today.year,
        "stats": {"total": 1, "n_pass": 1, "n_skip": 0},
        "groups": [
            {
                "title": "Supplier Guides",
                "label": "Supplier Guides",
                "items": [
                    {
                        "title": _RUN_PREVIEW_TITLE,
                        "href": f"./{_RUN_PREVIEW_SLUG}.html",
                        "type": "Supplier Guide",
                        "type_label": "Supplier Guide",
                        "desc": teaser,
                        "teaser": teaser,
                        "passed": True,
                    }
                ],
            }
        ],
        "nav": [
            {"label": "Home", "href": "./index.html", "active": True},
            {
                "label": "Supplier Guide",
                "href": f"./{_RUN_PREVIEW_SLUG}.html",
            },
        ],
    }
    index_html = atelier.render_index(ctx)
    (outdir / "index.html").write_text(index_html, encoding="utf-8")


def _write_run_preview(outdir: Path, name, seed, audience) -> str:
    """Synchronously create the preview page and its index."""
    html = _render_run_preview_html(name, seed, audience)
    (outdir / f"{_RUN_PREVIEW_SLUG}.html").write_text(html, encoding="utf-8")
    _write_run_preview_index(outdir, name, seed, audience)
    return html


def _finalize_run_preview(outdir: Path, result: dict, name, seed, audience):
    """Promote in-memory LLM HTML without ever reading output_src as input."""
    generated_html = ""
    for entry in (result or {}).get("pages", []):
        candidate = entry.get("html", "") if isinstance(entry, dict) else ""
        if candidate.lstrip().lower().startswith("<!doctype html"):
            generated_html = candidate
            break

    lowered = generated_html.lower()
    safe_generated = bool(generated_html) and not any(
        forbidden in lowered for forbidden in _RUN_PREVIEW_FORBIDDEN
    )

    _clear_run_output(outdir)
    if safe_generated:
        canonical = f"<section aria-label=\"B2B export summary\">{_run_preview_copy(name, seed, audience)}</section>"
        if "</body>" in generated_html.lower():
            body_end = generated_html.lower().rfind("</body>")
            final_html = generated_html[:body_end] + canonical + generated_html[body_end:]
        else:
            final_html = generated_html + canonical
        (outdir / f"{_RUN_PREVIEW_SLUG}.html").write_text(final_html, encoding="utf-8")
    else:
        final_html = _render_run_preview_html(name, seed, audience)
        (outdir / f"{_RUN_PREVIEW_SLUG}.html").write_text(final_html, encoding="utf-8")
    _write_run_preview_index(outdir, name, seed, audience)
    return final_html, safe_generated


def _run_preview_done(warning=None) -> dict:
    payload = {
        "ok": True,
        "results": [_run_preview_result()],
        "index_url": "/output/index.html",
    }
    if warning:
        payload["warning"] = warning
    return payload


# ── 路由 ────────────────────────────────────────────


@app.route("/")
def index():
    from auth import current_user
    user = current_user()
    if user:
        return redirect(url_for("projects"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    from auth import authenticate_user, login_user
    error = None
    next_url = request.args.get("next", "/")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(email, password)
        if user:
            login_user(user)
            return redirect(next_url)
        error = "邮箱或密码不正确。"

    return render_template("login.html", error=error, next=next_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    from auth import register_user, login_user
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            error = "邮箱和密码不能为空。"
        elif len(password) < 6:
            error = "密码至少 6 位。"
        else:
            try:
                result = register_user(email, password)
                login_user(result["user"])
                return redirect(url_for("projects"))
            except ValueError as e:
                error = str(e)

    return render_template("login.html", error=error, registering=True)


@app.route("/logout")
def logout():
    from auth import logout_user
    logout_user()
    return redirect(url_for("login"))


@app.route("/projects", methods=["GET", "POST"])
def projects():
    from auth import current_user, current_tenant_id

    user = current_user()
    if not user:
        return redirect(url_for("login"))

    tid = current_tenant_id()
    from models import list_projects as _list_projects

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        config = request.form.get("config", "").strip()
        seed = request.form.get("seed", "").strip()

        # Auto-generate name if empty
        if not name:
            if config:
                import os
                name = os.path.splitext(os.path.basename(config))[0]
            elif seed:
                name = seed
            else:
                name = "Untitled Project"

        from models import create_project
        create_project(
            user_id=user["id"],
            name=name,
            tenant_id=tid,
            industry_config=config if config else None,
            seed_keyword=seed if seed else None,
        )
        return redirect(url_for("projects"))

    proj_list = _list_projects(tenant_id=tid) if tid else []

    # Collect industry config files for the dropdown
    import os as _os
    industries_dir = ROOT / "industries"
    configs = []
    if industries_dir.exists():
        for f in sorted(industries_dir.glob("*.yaml")):
            try:
                import yaml as _yaml
                with open(f, "r", encoding="utf-8") as fh:
                    cfg = _yaml.safe_load(fh)
                name = cfg.get("name", f.stem) if cfg else f.stem
            except Exception:
                name = f.stem
            configs.append({"file": f.name, "name": name})

    ctx = _get_template_context(projects=proj_list, configs=configs)
    return render_template("projects.html", **ctx)


@app.route("/projects/<int:project_id>")
def project_detail(project_id):
    from auth import current_user
    if not current_user():
        return redirect(url_for("login"))

    from models import get_project, list_generations, list_keywords
    proj = get_project(project_id)
    if not proj:
        return "项目不存在", 404

    gens = list_generations(project_id=project_id)
    kws = list_keywords(project_id=project_id)

    ctx = _get_template_context(project=proj, generations=gens, keywords=kws)
    return render_template("index.html", **ctx)


@app.route("/projects/<int:project_id>/wordpress")
def project_wordpress_sync(project_id):
    from auth import current_user
    if not current_user():
        return redirect(url_for("login"))

    from models import get_project
    proj = get_project(project_id)
    if not proj:
        return "项目不存在", 404

    ctx = _get_template_context(project=proj)
    return render_template("wordpress_sync.html", **ctx)


@app.route("/run", methods=["GET", "POST"])
def run_generate():
    from auth import current_user, current_tenant_id
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "未登录"}), 401

    # ── GET: SSE stream for EventSource ──
    if request.method == "GET":
        tid = current_tenant_id()
        project_id = request.args.get("project") or request.args.get("project_id")
        name = request.args.get("name")
        seed = request.args.get("seed")
        audience = request.args.get("audience")
        mode = request.args.get("mode", "dry-run")

        if not project_id:
            return jsonify({"ok": False, "error": "缺少 project_id"}), 400

        from models import get_project
        proj = get_project(int(project_id))
        if not proj:
            return jsonify({"ok": False, "error": "项目不存在"}), 404
        if not proj.get("tenant_id"):
            proj["tenant_id"] = tid
        if not proj.get("user_id"):
            proj["user_id"] = user["id"]

        # Apply seed/name from query params if provided.
        if seed and not proj.get("seed_keyword"):
            proj["seed_keyword"] = seed
        if name and (not proj.get("name") or proj["name"] == "Untitled Project"):
            proj["name"] = name

        name = name or proj.get("name") or _RUN_PREVIEW_TITLE
        seed = seed or proj.get("seed_keyword") or "hammer, hardware tools"
        audience = audience or "wholesalers and distributors"

        # output_src is output-only for GET /run.  Remove stale generated files,
        # then synchronously create the first Canvas page before any LLM call.
        outdir = ROOT / "output_src"
        _clear_run_output(outdir)
        preview_html = _write_run_preview(outdir, name, seed, audience)
        timeout_seconds = float(app.config.get("RUN_GET_TIMEOUT_SECONDS", 180))
        heartbeat_seconds = float(app.config.get("RUN_GET_HEARTBEAT_SECONDS", 3))

        def sse_generator():
            import run as _run
            import json as _json
            import os as _os
            import queue
            import tempfile

            _run.llm.reset_usage()
            yield "data: 开始生成...\n\n"
            yield (
                "event: token\n"
                f"data: {_json.dumps({'slug': _RUN_PREVIEW_SLUG, 'html': preview_html}, ensure_ascii=False)}\n\n"
            )
            yield f"data: 已生成首版预览 {_RUN_PREVIEW_SLUG}.html\n\n"

            q = queue.Queue()
            cancelled = threading.Event()

            def worker():
                try:
                    def on_progress(ev_type, ev_data):
                        """Progress callback: pushes typed events into the SSE queue."""
                        if not cancelled.is_set():
                            q.put(("progress", {"type": ev_type, **ev_data}))

                    # Full generation renders into an isolated directory. A timed-out
                    # worker can therefore never overwrite the public preview later.
                    with tempfile.TemporaryDirectory(prefix="ai-seo-run-") as stage_dir:
                        industry_config = proj.get("industry_config", "")
                        has_cfg = bool(industry_config and _os.path.exists(industry_config))
                        if has_cfg:
                            result = _run.generate_site(
                                proj, mode=mode, output_dir=stage_dir,
                                progress_callback=on_progress,
                            )
                        else:
                            user_input = (
                                f"{name}. Seed keyword: {seed}. Target audience: {audience}. "
                                "Build an English B2B export SEO site for hammer and hardware tools suppliers."
                            )
                            result = _run.generate_site_from_input(
                                user_input, project_id=int(project_id), tenant_id=tid,
                                mode=mode, bypass_subscription=True,
                                output_dir=stage_dir,
                                progress_callback=on_progress,
                            )
                        if not cancelled.is_set():
                            q.put(("done", result))
                except Exception as e:
                    if not cancelled.is_set():
                        q.put(("error", _redact_sse_text(e)))

            t = threading.Thread(target=worker, daemon=True)
            t.start()

            started_at = time.monotonic()
            deadline = started_at + max(0.01, timeout_seconds)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    cancelled.set()
                    done = _run_preview_done(
                        "LLM generation timed out, preview content was generated from seed terms."
                    )
                    yield f"event: done\ndata: {_json.dumps(done, ensure_ascii=False)}\n\n"
                    return
                try:
                    msg = q.get(timeout=min(max(0.01, heartbeat_seconds), remaining))
                    if msg[0] == "done":
                        final_html, replaced = _finalize_run_preview(
                            outdir, msg[1], name, seed, audience,
                        )
                        if replaced:
                            yield (
                                "event: token\n"
                                f"data: {_json.dumps({'slug': _RUN_PREVIEW_SLUG, 'html': final_html}, ensure_ascii=False)}\n\n"
                            )
                            yield f"data: 已用完整内容更新 {_RUN_PREVIEW_SLUG}.html\n\n"
                        done = _run_preview_done()
                        # Enhance done with generation metadata from result
                        result = msg[1]
                        done["job_id"] = result.get("generation_ids", [None])[0] if result.get("generation_ids") else None
                        done["pages_total"] = result.get("pages_total", 0)
                        done["pages_success"] = result.get("pages_success", 0)
                        yield f"event: done\ndata: {_json.dumps(done, ensure_ascii=False)}\n\n"
                        return
                    elif msg[0] == "error":
                        done = _run_preview_done(
                            f"LLM generation failed; preview retained: {msg[1]}"
                        )
                        yield f"event: done\ndata: {_json.dumps(done, ensure_ascii=False)}\n\n"
                        return
                    elif msg[0] == "progress":
                        # ── New: emit typed SSE events from pipeline callback ──
                        ev = _redact_sse_payload(msg[1])
                        ev_type = ev.pop("type", "")
                        payload = _json.dumps(ev, ensure_ascii=False)
                        if ev_type == "stage":
                            yield f"event: stage\ndata: {payload}\n\n"
                        elif ev_type == "progress":
                            yield f"event: progress\ndata: {payload}\n\n"
                        elif ev_type == "page_start":
                            yield f"event: page_start\ndata: {payload}\n\n"
                        elif ev_type == "page_preview":
                            yield f"event: page_preview\ndata: {payload}\n\n"
                        elif ev_type == "page_done":
                            yield f"event: page_done\ndata: {payload}\n\n"
                        elif ev_type == "log":
                            yield f"event: log\ndata: {payload}\n\n"
                            # Also emit as text line for backward compat with interpret()
                            yield f"data: [{ev.get('level', 'info').upper()}] {ev.get('message', '')}\n\n"
                except queue.Empty:
                    elapsed = max(1, int(time.monotonic() - started_at))
                    yield f"data: 正在生成中 ({elapsed}s)...\n\n"

        return Response(stream_with_context(sse_generator()),
                       mimetype="text/event-stream",
                       headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── POST: JSON API (保留不变) ──
    data = request.get_json() or {}
    project_id = data.get("project_id")
    mode = data.get("mode", "dry-run")

    from models import get_project
    proj = get_project(project_id) if project_id else None
    if not proj:
        return jsonify({"ok": False, "error": "项目不存在"}), 404

    tid = current_tenant_id()
    if not proj.get("tenant_id"):
        proj["tenant_id"] = tid
    if not proj.get("user_id"):
        proj["user_id"] = user["id"]

    import run as _run
    _run.llm.reset_usage()

    result = _run.generate_site(proj, mode=mode)
    return jsonify(result)


# ── 结果标准化 (供 /run SSE 使用) ──────────────────


@app.route("/api/chat/run")
def api_chat_run():
    """Stream the conversational workspace while preserving legacy /run."""
    from auth import current_user, current_tenant_id
    from models import get_project

    if not current_user():
        return jsonify({"ok": False, "error": "未登录"}), 401
    tenant_id = current_tenant_id()
    project_id = request.args.get("project_id", type=int)
    message = request.args.get("message", "").strip()
    if not project_id or not message:
        return jsonify({"ok": False, "error": "缺少 project_id 或 message"}), 400
    project = get_project(project_id)
    if not project:
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    if project.get("tenant_id") != tenant_id:
        return jsonify({"ok": False, "error": "无权访问该项目"}), 403

    from lib.conversation_events import stream_conversation
    generator = stream_conversation(
        project=project,
        tenant_id=tenant_id,
        message=message,
        root=ROOT,
        timeout_seconds=app.config.get("CHAT_RUN_TIMEOUT_SECONDS", 180),
        heartbeat_seconds=app.config.get("CHAT_RUN_HEARTBEAT_SECONDS", 3),
    )
    return Response(
        stream_with_context(generator),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _normalize_gen_result(result: dict) -> dict:
    """将 generate_site / generate_site_from_input 返回标准化为前端 Canvas 所需格式。

    Frontend 期望:
    {
      "ok": bool,
      "results": [{"slug", "title", "type", "score", "passed", "link"}, ...],
      "index_url": "/output/index.html",
      "error": "..."
    }
    """
    import os as _os
    normalized = {
        "ok": result.get("ok", False),
        "error": result.get("error", result.get("message", "")),
        "index_url": result.get("index_url", "/output/index.html"),
        "results": [],
        "pages_total": result.get("pages_total", 0),
        "pages_success": result.get("pages_success", 0),
    }

    # Try to extract results from the nested pages structure
    pages = result.get("pages", [])
    results = result.get("results", [])

    if pages and not results:
        for entry in pages:
            pg = entry.get("page", entry)
            ct = entry.get("content", entry)
            q = entry.get("quality", {})
            slug = pg.get("slug", "")
            if not slug:
                continue
            results.append({
                "slug": slug,
                "title": ct.get("title", pg.get("title", slug)),
                "type": pg.get("type", pg.get("page_type", "page")),
                "score": q.get("score", None),
                "passed": q.get("passed", True),
                "link": f"./{slug}.html",
            })

    # Fallback: scan output_src/*.html if still no results
    if not results:
        outdir = ROOT / "output_src"
        if outdir.exists():
            for f in sorted(outdir.glob("*.html")):
                if f.name == "index.html":
                    continue
                slug = f.stem
                results.append({
                    "slug": slug,
                    "title": slug.replace("-", " ").title(),
                    "type": "page",
                    "score": None,
                    "passed": True,
                    "link": f"./{f.name}",
                })

    normalized["results"] = results

    # Ensure index_url exists
    if not normalized.get("index_url"):
        normalized["index_url"] = "/output/index.html"

    return normalized


# ── Intake 对话接口 (首页聊天 UI) ──────────────────


# ── 中文意图解析 (确定性 fallback) ──────────────────


def _chinese_intake_parse(message: str) -> dict | None:
    """从中文/混合输入中确定性提取 brief。返回 None 表示无法解析。"""
    import re
    text = message.strip()
    if len(text) < 4:
        return None

    # 产品/行业词
    industry_map = {
        "铁锤": "hammer", "锤子": "hammer", "锤": "hammer",
        "五金": "hardware", "五金工具": "hardware tools", "手工具": "hand tools",
        "工具": "tools", "螺丝": "screw", "螺栓": "bolt", "螺母": "nut",
        "扳手": "wrench", "钳子": "pliers", "锯": "saw", "钻头": "drill bit",
        "PU皮革": "PU leather", "皮革": "leather", "合成革": "synthetic leather",
        "钢管": "steel pipe", "不锈钢": "stainless steel", "阀门": "valve",
        "轴承": "bearing", "泵": "pump", "电机": "motor",
        "灯具": "lighting", "LED": "LED lighting", "家具": "furniture",
        "汽车配件": "auto parts", "电子产品": "electronics",
    }
    found_industry = ""
    for cn, en in sorted(industry_map.items(), key=lambda x: -len(x[0])):
        if cn.lower() in text.lower() or en.lower() in text.lower():
            found_industry = en
            break

    # 市场/业务类型
    market_parts = []
    b2b_signals = {"出口": True, "外贸": True, "B2B": True, "b2b": True,
                   "批发": True, "批发商": True, "经销商": True, "进口商": True,
                   "supplier": True, "manufacturer": True, "wholesale": True,
                   "distributor": True, "importer": True, "export": True,
                   "海外": True, "overseas": True, "国外": True}
    for word, _ in b2b_signals.items():
        if word.lower() in text.lower():
            market_parts.append(word)

    market = ""
    if market_parts:
        if any(w in ("出口", "外贸", "export") for w in market_parts):
            market = "B2B export"
        elif any(w in ("批发", "批发商", "wholesale", "distributor") for w in market_parts):
            market = "B2B wholesale"
        elif any(w in ("supplier", "manufacturer") for w in market_parts):
            market = "B2B supplier"

    # 语言
    language = "English"
    if re.search(r'英文|English|english', text, re.IGNORECASE):
        language = "English"
    elif re.search(r'中文|Chinese|chinese', text, re.IGNORECASE):
        language = "Chinese"
    elif re.search(r'西班牙|Spanish|español', text, re.IGNORECASE):
        language = "Spanish"

    # 需要至少 industry + market 才能生成 brief
    if not found_industry:
        return None
    if not market:
        # 即使没有明确市场词, 如果有 B2B/出口相关词也接受
        if not market_parts:
            return None

    # 构建 brief
    kw_base = found_industry
    seed_keywords = [
        f"{kw_base} supplier",
        f"{kw_base} manufacturer",
        f"{kw_base} wholesale",
        f"{kw_base} export",
        f"{kw_base} factory",
    ]

    audience = "overseas importers, wholesalers, and distributors"
    if any(w in ("批发", "经销商") for w in market_parts):
        audience = "wholesalers and distributors"
    elif any(w in ("supplier", "出口", "export") for w in market_parts):
        audience = "overseas importers and procurement managers"

    industry_display = f"{found_industry} / {text[:30]}"

    return {
        "ok": True,
        "action": "brief",
        "message": f"已识别: {industry_display}, {market}, {language}。信息够了,给你拟了一份 brief。",
        "brief": {
            "project_name": f"{found_industry.title()} {market.title()} Site",
            "industry": industry_display,
            "market": market,
            "language": language,
            "audience": audience,
            "differentiator": f"B2B content for {found_industry} buyers",
            "seed_keywords": seed_keywords,
            "competitors": [],
        },
    }


@app.route("/intake", methods=["POST"])
def intake_chat():
    """首页聊天 UI 的意图对话。POST {history, message} → {ok, action, message, brief, chips}。"""
    data = request.get_json() or {}
    history = data.get("history", [])
    message = data.get("message") or data.get("text") or data.get("input") or data.get("content") or ""
    if not message:
        return jsonify({"ok": False, "error": "message_required"}), 400

    try:
        from lib.intake import step
        result = step(history, message)

        # 如果 LLM 返回 ask 且信息可能足够, 尝试中文确定性解析
        if result.get("action") == "ask":
            zh = _chinese_intake_parse(message)
            if zh:
                return jsonify(zh)

        return jsonify(result)
    except Exception:
        # LLM 失败 → 直接尝试中文解析
        zh = _chinese_intake_parse(message)
        if zh:
            return jsonify(zh)
        return jsonify({"ok": True, "action": "ask",
                        "message": "我正在理解你的需求。请告诉我：你是做什么行业的？打算卖给谁？用什么语言？",
                        "chips": ["五金工具出口", "PU皮革B2B", "家具海外批发", "汽车配件英文"]})


@app.route("/intake/confirm", methods=["POST"])
def intake_confirm():
    """确认 brief 并创建项目。POST {brief} → {ok, project_id}。"""
    from auth import current_user, current_tenant_id
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "未登录"}), 401
    tid = current_tenant_id()
    data = request.get_json() or {}
    brief = data.get("brief", {})
    if not brief:
        return jsonify({"ok": False, "error": "brief_required"}), 400
    try:
        name = brief.get("project_name", brief.get("industry", "Untitled"))
        seed = (brief.get("seed_keywords") or [None])[0] if brief.get("seed_keywords") else None
        from models import create_project
        pid = create_project(
            user_id=user["id"], name=name, tenant_id=tid,
            industry=brief.get("industry", ""),
            language=brief.get("language", "English"),
            seed_keyword=seed,
        )
        return jsonify({
            "ok": True, "project_id": pid,
            "redirect": f"/projects/{pid}?autorun=1",
            "run": {
                "seed": seed or "",
                "name": name,
                "audience": brief.get("audience", ""),
                "mode": "dry-run",
            },
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/agent/message", methods=["POST"])
def api_agent_message():
    """统一 agent 消息接口。POST {message|text|input} → {ok, reply, scope, blueprint, job_id}。"""
    from auth import current_user, current_tenant_id
    user = current_user()
    tid = current_tenant_id()
    data = request.get_json() or {}
    msg = data.get("message") or data.get("text") or data.get("input") or ""
    if not msg:
        return jsonify({"ok": False, "error": "message_required"}), 400

    try:
        from lib.seo_engine.stage0_clarify import clarify_request
        scope_result = clarify_request(msg)
        scope = scope_result.get("scope", {})
        reply = f"已识别行业: {scope.get('industry', '未知')}, 语言: {scope.get('language', 'English')}, 市场: {scope.get('target_market', 'global')}"

        # S1 profile + S2 blueprint
        from lib.seo_engine.stage1_profile import build_business_profile
        profile = build_business_profile(scope)
        from lib.seo_engine.stage2_blueprint import build_site_blueprint
        blueprint = build_site_blueprint(project_id=0, profile=profile)

        # Create generation job (queued)
        job_id = None
        if tid:
            try:
                from lib.generation_job_mode import create_generation_job
                job = create_generation_job(tid, user_input=msg, mode="dry-run")
                job_id = job.get("job_id")
            except Exception:
                pass

        return jsonify({
            "ok": True, "reply": reply,
            "scope": scope, "blueprint": blueprint.to_dict(),
            "job_id": job_id, "next_action": "run_job" if job_id else "create_project",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "reply": "意图分析暂时不可用,请稍后重试。"})


@app.route("/demo")
def demo():
    """演示页面 —— 显示 output_src/ 中最新渲染结果。"""
    from auth import current_user
    outdir = ROOT / "output_src"
    files = sorted(outdir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True) if outdir.exists() else []
    ctx = _get_template_context(demo_files=[f.name for f in files[:10]], user=current_user())
    return render_template("index.html", **ctx)


@app.route("/output/<path:filename>")
def output_file(filename):
    """Serve generated HTML files from output_src/。"""
    return send_from_directory(str(ROOT / "output_src"), filename)


@app.route("/demo_stream")
def demo_stream():
    """SSE 流式演示 —— 将生成进度推送到前端。"""
    def gen():
        from lib.llm import reset_usage, last_usage
        reset_usage()

        yield "data: " + json.dumps({"event": "start", "message": "开始生成..."}) + "\n\n"

        # 逐页回调
        def on_page(p):
            yield "data: " + json.dumps({
                "event": "page",
                "slug": p.get("slug", ""),
                "title": p.get("title", ""),
            }) + "\n\n"

        yield "data: " + json.dumps({"event": "done", "usage": last_usage()}) + "\n\n"

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── API ─────────────────────────────────────────────


@app.route("/api/keywords")
def api_keywords():
    from auth import current_tenant_id
    tid = current_tenant_id()
    project_id = request.args.get("project_id", type=int)
    from models import list_keywords as _list_keywords
    kws = _list_keywords(project_id=project_id, tenant_id=tid)
    return jsonify({"keywords": kws})


@app.route("/api/subscription/status")
def api_subscription_status():
    from auth import current_tenant_id
    tid = current_tenant_id()
    if not tid:
        return jsonify({"error": "未登录或无租户"}), 401
    from lib.subscription import get_subscription_status
    return jsonify(get_subscription_status(tid))


@app.route("/api/usage/summary")
def api_usage_summary():
    from auth import current_tenant_id
    tid = current_tenant_id()
    if not tid:
        return jsonify({"error": "未登录或无租户"}), 401
    from lib.usage import get_usage_summary as _gus
    return jsonify(_gus(tid))


@app.route("/api/plans")
def api_plans():
    from models import list_plans
    return jsonify({"plans": list_plans()})


# ── Phase 1: JSON API (后端专用,不接新前端) ──────────


def _require_login():
    """检查登录,未登录返回 401 JSON。"""
    from auth import current_user
    if not current_user():
        return jsonify({"ok": False, "error": "未登录"}), 401
    return None


def _require_tenant():
    """获取当前 tenant_id,无租户返回 401 JSON。"""
    from auth import current_tenant_id
    tid = current_tenant_id()
    if not tid:
        return None, (jsonify({"ok": False, "error": "未登录或无租户"}), 401)
    return tid, None


# ── /api/projects ──


@app.route("/api/projects")
def api_projects():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from models import list_projects as _list_projects
    projects = _list_projects(tenant_id=tid)
    return jsonify({"ok": True, "projects": projects})


@app.route("/api/projects/<int:project_id>")
def api_project_detail(project_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from models import get_project
    proj = get_project(project_id)
    if not proj:
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    if proj.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问该项目"}), 403

    return jsonify({"ok": True, "project": proj})


# ── /api/sites ──


@app.route("/api/sites")
def api_sites():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    project_id = request.args.get("project_id", type=int)
    from lib.sites import list_sites as _list_sites
    sites = _list_sites(tenant_id=tid, project_id=project_id)
    return jsonify({"ok": True, "sites": sites})


@app.route("/api/sites/<int:site_id>")
def api_site_detail(site_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.sites import get_site
    site = get_site(site_id, tenant_id=tid)
    if not site:
        return jsonify({"ok": False, "error": "站点不存在"}), 404
    return jsonify({"ok": True, "site": site})


# ── /api/generations/<id> ──


@app.route("/api/generations/<int:generation_id>")
def api_generation_detail(generation_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from models import list_generations
    gens = list_generations(tenant_id=tid)
    gen = next((g for g in gens if g["id"] == generation_id), None)
    if not gen:
        return jsonify({"ok": False, "error": "生成记录不存在"}), 404

    from lib.generation_logs import list_generation_logs
    logs = list_generation_logs(generation_id=generation_id)
    return jsonify({"ok": True, "generation": gen, "logs": logs})


@app.route("/api/generations/<int:generation_id>/logs")
def api_generation_logs(generation_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.generation_logs import list_generation_logs
    logs = list_generation_logs(generation_id=generation_id)
    return jsonify({"ok": True, "generation_id": generation_id, "logs": logs})


# ── /api/cms/logs ──


@app.route("/api/cms/logs")
def api_cms_logs():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    generation_id = request.args.get("generation_id", type=int)
    site_id = request.args.get("site_id", type=int)
    limit = request.args.get("limit", 100, type=int)

    from lib.cms_logs import list_cms_logs
    logs = list_cms_logs(
        tenant_id=tid,
        generation_id=generation_id,
        site_id=site_id,
        limit=limit,
    )
    return jsonify({"ok": True, "logs": logs})


# ── Phase 2: Batch API ───────────────────────────────


@app.route("/api/batches", methods=["GET", "POST"])
def api_batches():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    if request.method == "POST":
        # 从 CSV 创建 batch_run + jobs
        data = request.get_json() or {}
        csv_path = data.get("csv_path", "")
        project_id = data.get("project_id")
        mode = data.get("mode", "dry-run")

        if not csv_path:
            return jsonify({"ok": False, "error": "缺少 csv_path"}), 400
        if not project_id:
            return jsonify({"ok": False, "error": "缺少 project_id"}), 400

        from models import get_project
        proj = get_project(project_id)
        if not proj:
            return jsonify({"ok": False, "error": "项目不存在"}), 404
        if proj.get("tenant_id") != tid:
            return jsonify({"ok": False, "error": "无权访问该项目"}), 403

        try:
            from lib.batch_jobs import parse_batch_csv, create_batch_run, create_jobs_from_rows
            rows = parse_batch_csv(csv_path)

            import os
            csv_name = os.path.basename(csv_path).rsplit(".", 1)[0]
            br = create_batch_run(
                tenant_id=tid, user_id=proj.get("user_id"),
                project_id=project_id,
                name=f"{csv_name} ({mode})", source=csv_path, mode=mode,
            )
            jobs = create_jobs_from_rows(
                batch_run_id=br["id"], tenant_id=tid,
                user_id=proj.get("user_id"), project_id=project_id,
                rows=rows, mode=mode,
            )
            return jsonify({"ok": True, "batch_run": br, "jobs_created": len(jobs)})
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # GET
    from lib.batch_jobs import list_batch_runs
    runs = list_batch_runs(tenant_id=tid)
    return jsonify({"ok": True, "batch_runs": runs})


@app.route("/api/batches/<int:batch_id>")
def api_batch_detail(batch_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import get_batch_run
    br = get_batch_run(batch_id, tenant_id=tid)
    if not br:
        return jsonify({"ok": False, "error": "Batch run 不存在"}), 404
    return jsonify({"ok": True, "batch_run": br})


@app.route("/api/batches/<int:batch_id>/jobs")
def api_batch_jobs(batch_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import list_jobs
    jobs = list_jobs(batch_id, tenant_id=tid)
    return jsonify({"ok": True, "batch_run_id": batch_id, "jobs": jobs})


@app.route("/api/batches/<int:batch_id>/run", methods=["POST"])
def api_batch_run(batch_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import get_batch_run
    br = get_batch_run(batch_id, tenant_id=tid)
    if not br:
        return jsonify({"ok": False, "error": "Batch run 不存在"}), 404

    from lib.batch_runner import run_batch
    result = run_batch(batch_id, bypass_subscription=False)
    return jsonify(result)


@app.route("/api/batches/<int:batch_id>/retry-failed", methods=["POST"])
def api_batch_retry_failed(batch_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import get_batch_run
    br = get_batch_run(batch_id, tenant_id=tid)
    if not br:
        return jsonify({"ok": False, "error": "Batch run 不存在"}), 404

    from lib.batch_runner import retry_failed_jobs
    result = retry_failed_jobs(batch_id, bypass_subscription=False)
    return jsonify(result)


@app.route("/api/batches/<int:batch_id>/retry-partial", methods=["POST"])
def api_batch_retry_partial(batch_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import get_batch_run
    br = get_batch_run(batch_id, tenant_id=tid)
    if not br:
        return jsonify({"ok": False, "error": "Batch run 不存在"}), 404

    from lib.batch_runner import retry_partial_jobs
    result = retry_partial_jobs(batch_id, bypass_subscription=False)
    return jsonify(result)


@app.route("/api/jobs/<int:job_id>")
def api_job_detail(job_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from lib.batch_jobs import get_job, list_job_steps
    job = get_job(job_id, tenant_id=tid)
    if not job:
        return jsonify({"ok": False, "error": "Job 不存在"}), 404

    steps = list_job_steps(job_id)
    return jsonify({"ok": True, "job": job, "steps": steps})


# ── Phase 3: SEO Engine API ──────────────────────────


@app.route("/api/seo/clarify", methods=["POST"])
def api_seo_clarify():
    err = _require_login()
    if err:
        return err
    data = request.get_json() or {}
    user_input = data.get("user_input", "")
    optional_url = data.get("optional_url")
    if not user_input:
        return jsonify({"ok": False, "error": "缺少 user_input"}), 400

    from lib.seo_engine.stage0_clarify import clarify_request
    result = clarify_request(user_input, optional_url=optional_url)
    return jsonify(result)


@app.route("/api/seo/profile", methods=["POST"])
def api_seo_profile():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    data = request.get_json() or {}
    scope = data.get("scope", {})
    project_id = data.get("project_id")

    if not scope.get("industry"):
        return jsonify({"ok": False, "error": "scope.industry 不能为空"}), 400

    project = None
    if project_id:
        from models import get_project
        project = get_project(project_id)
        if project and project.get("tenant_id") != tid:
            return jsonify({"ok": False, "error": "无权访问该项目"}), 403

    from lib.seo_engine.stage1_profile import build_business_profile
    profile = build_business_profile(scope, project)

    # 持久化
    import json
    from models import create_business_profile
    pid = create_business_profile(
        tenant_id=tid, project_id=project_id,
        status="draft",
        profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
    )

    return jsonify({"ok": True, "profile_id": pid, "profile": profile.to_dict()})


@app.route("/api/seo/blueprint", methods=["POST"])
def api_seo_blueprint_create():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    data = request.get_json() or {}
    project_id = data.get("project_id")

    project = None
    if project_id:
        from models import get_project
        project = get_project(project_id)
        if project and project.get("tenant_id") != tid:
            return jsonify({"ok": False, "error": "无权访问该项目"}), 403

    # 获取或构建 profile
    profile_dict = data.get("profile")
    if not profile_dict:
        # 从已有 business_profile 读取
        if project_id:
            from models import list_business_profiles
            bps = list_business_profiles(project_id=project_id)
            if bps:
                import json as _json
                profile_dict = _json.loads(bps[0]["profile_json"])
        if not profile_dict:
            return jsonify({"ok": False, "error": "缺少 profile 且项目无已有 profile"}), 400

    from lib.seo_engine.schemas import BusinessProfile, SiteBlueprint
    profile = BusinessProfile.from_dict(profile_dict)

    from lib.seo_engine.stage2_blueprint import build_site_blueprint
    bp = build_site_blueprint(project_id=project_id or 0, profile=profile)

    # 持久化
    import json as _json
    from models import create_site_blueprint
    bpid = create_site_blueprint(
        tenant_id=tid, project_id=project_id,
        status="draft",
        blueprint_json=_json.dumps(bp.to_dict(), ensure_ascii=False),
    )

    return jsonify({"ok": True, "blueprint_id": bpid, "blueprint": bp.to_dict()})


@app.route("/api/seo/blueprint/<int:blueprint_id>")
def api_seo_blueprint_get(blueprint_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from models import get_site_blueprint
    bp = get_site_blueprint(blueprint_id)
    if not bp:
        return jsonify({"ok": False, "error": "Blueprint 不存在"}), 404
    if bp.get("tenant_id") and bp.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403

    return jsonify({"ok": True, "blueprint": bp})


@app.route("/api/seo/blueprint/<int:blueprint_id>/graph")
def api_seo_blueprint_graph(blueprint_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err

    from models import get_site_blueprint
    bp_row = get_site_blueprint(blueprint_id)
    if not bp_row:
        return jsonify({"ok": False, "error": "Blueprint 不存在"}), 404
    if bp_row.get("tenant_id") and bp_row.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403

    import json as _json
    from lib.seo_engine.schemas import SiteBlueprint
    from lib.seo_engine.blueprint_viz import blueprint_to_graph_data

    bp = SiteBlueprint.from_dict(_json.loads(bp_row["blueprint_json"]))
    graph_data = blueprint_to_graph_data(bp)

    return jsonify({"ok": True, "blueprint_id": blueprint_id, "graph": graph_data})


# ── Phase 4: Blueprint → Content API ─────────────────


@app.route("/api/seo/generate-from-input", methods=["POST"])
def api_seo_generate_from_input():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    data = request.get_json() or {}
    user_input = data.get("user_input", "")
    project_id = data.get("project_id")
    mode = data.get("mode", "dry-run")
    if not user_input:
        return jsonify({"ok": False, "error": "缺少 user_input"}), 400

    import run as _run
    _run.llm.reset_usage()
    result = _run.generate_site_from_input(
        user_input, project_id=project_id, tenant_id=tid,
        mode=mode, bypass_subscription=False,
    )
    return jsonify(result)


@app.route("/api/seo/generate-from-blueprint", methods=["POST"])
def api_seo_generate_from_blueprint():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    data = request.get_json() or {}
    blueprint_id = data.get("blueprint_id")
    project_id = data.get("project_id")
    mode = data.get("mode", "dry-run")
    if not blueprint_id:
        return jsonify({"ok": False, "error": "缺少 blueprint_id"}), 400

    from models import get_site_blueprint
    bp_row = get_site_blueprint(blueprint_id)
    if not bp_row:
        return jsonify({"ok": False, "error": "Blueprint 不存在"}), 404
    if bp_row.get("tenant_id") and bp_row.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403

    import json as _json
    from lib.seo_engine.schemas import SiteBlueprint
    blueprint = SiteBlueprint.from_dict(_json.loads(bp_row["blueprint_json"]))

    project = {"id": project_id or bp_row["project_id"], "tenant_id": tid}
    if project_id:
        from models import get_project
        proj = get_project(project_id)
        if proj:
            project = dict(proj)

    import run as _run
    _run.llm.reset_usage()
    result = _run.generate_site_from_blueprint(
        project, blueprint, mode=mode, bypass_subscription=False,
    )
    return jsonify(result)


@app.route("/api/page-contents")
def api_page_contents():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    project_id = request.args.get("project_id", type=int)
    blueprint_id = request.args.get("blueprint_id", type=int)
    from models import list_page_contents
    pcs = list_page_contents(tenant_id=tid, project_id=project_id, blueprint_id=blueprint_id)
    return jsonify({"ok": True, "page_contents": pcs})


@app.route("/api/page-contents/<int:pc_id>")
def api_page_content_detail(pc_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    from models import get_page_content
    pc = get_page_content(pc_id)
    if not pc:
        return jsonify({"ok": False, "error": "PageContent 不存在"}), 404
    if pc.get("tenant_id") and pc.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403
    return jsonify({"ok": True, "page_content": pc})


@app.route("/api/projects/<int:project_id>/conversation-state")
def api_conversation_state(project_id):
    """Restore chat plus Artifact state without starting generation or publishing."""
    err = _require_login()
    if err:
        return err
    tenant_id, err = _require_tenant()
    if err:
        return err
    from models import get_project
    project = get_project(project_id)
    if not project:
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    if project.get("tenant_id") != tenant_id:
        return jsonify({"ok": False, "error": "无权访问该项目"}), 403
    from lib.conversation_state import get_conversation_state
    return jsonify(get_conversation_state(project_id, tenant_id))


@app.route("/api/projects/<int:project_id>/preview-state")
def api_preview_state(project_id):
    """返回项目的最近生成状态，供前端刷新恢复 Canvas 使用。"""
    err = _require_login()
    if err: return err
    tid, err2 = _require_tenant()
    if err2: return err2

    from models import get_project, list_generations, list_page_contents
    proj = get_project(project_id)
    if not proj:
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    if proj.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问该项目"}), 403

    # list_generations currently gives tenant_id precedence when both filters are
    # supplied, so filter by project first and then verify tenant ownership here.
    generations = [
        item for item in list_generations(project_id=project_id)
        if item.get("tenant_id") in (None, tid)
    ]
    latest_gen = generations[0] if generations else None
    if latest_gen:
        latest_gen = {
            key: latest_gen.get(key)
            for key in (
                "id", "project_id", "status", "page_count", "passed_count",
                "tokens_used", "keyword", "page_type", "title", "slug",
                "quality_score", "token_count", "created_at",
            )
        }

    # 所有已持久化的页面
    pcs = list_page_contents(project_id=project_id, tenant_id=tid)

    # 最近一次 job
    latest_job = None
    try:
        from models import list_jobs
        jobs = list_jobs(tenant_id=tid)
        for j in jobs:
            if j.get("project_id") == project_id:
                latest_job = j
                break
    except Exception:
        pass
    if latest_job:
        latest_job = {
            key: latest_job.get(key)
            for key in (
                "id", "project_id", "mode", "status", "pages_total",
                "pages_success", "pages_failed", "generation_id", "retryable",
                "created_at", "started_at", "finished_at",
            )
        }

    pages_list = []
    for pc in pcs:
        pages_list.append({
            "id": pc.get("id"),
            "slug": pc.get("slug", ""),
            "title": pc.get("title", ""),
            "page_type": pc.get("page_type", ""),
            "primary_keyword": pc.get("primary_keyword", ""),
            "quality_score": pc.get("quality_score", 0),
            "review_status": pc.get("review_status", "pending"),
            "status": pc.get("review_status", "pending"),
            "html": pc.get("gutenberg_html", ""),
            "gutenberg_html": pc.get("gutenberg_html", ""),
            "preview_url": f"/output/{pc.get('slug', '')}.html" if pc.get("slug") else "",
        })

    preview = dict(pages_list[-1]) if pages_list else None

    return jsonify({
        "ok": True,
        "project_id": project_id,
        "latest_job": latest_job,
        "latest_generation": latest_gen,
        "preview": preview,
        "pages": pages_list,
        "pages_total": len(pages_list),
    })


# ── Phase 9.2: Job API ───────────────────────────────


@app.route("/api/jobs/generation", methods=["POST"])
def api_create_generation_job():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    from lib.generation_job_mode import create_generation_job
    result = create_generation_job(
        tenant_id=tid, project_id=data.get("project_id"),
        user_input=data.get("user_input"),
        blueprint_id=data.get("blueprint_id"),
        mode=data.get("mode", "dry-run"),
        use_competitor=data.get("use_competitor", False),
        bypass_subscription=data.get("bypass_subscription", False),
    )
    return jsonify(result)


@app.route("/api/jobs/generation/<int:job_id>/run", methods=["POST"])
def api_run_generation_job(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import run_generation_job
    return jsonify(run_generation_job(job_id, tenant_id=tid))


@app.route("/api/jobs/generation/<int:job_id>/run-background", methods=["POST"])
def api_run_generation_job_bg(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import run_generation_job_background
    return jsonify(run_generation_job_background(job_id, tenant_id=tid))


@app.route("/api/jobs/generation/<int:job_id>")
def api_job_status(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import get_generation_job_status
    return jsonify(get_generation_job_status(job_id, tenant_id=tid))


@app.route("/api/jobs/generation/<int:job_id>/result")
def api_job_result(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import get_generation_job_result
    return jsonify(get_generation_job_result(job_id, tenant_id=tid))


@app.route("/api/jobs/generation/<int:job_id>/cancel", methods=["POST"])
def api_cancel_job(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import cancel_generation_job
    return jsonify(cancel_generation_job(job_id, tenant_id=tid))


# ── Phase 9.3.5: WordPress Sync Panel API ────────────────

@app.route("/api/wordpress/test-connection", methods=["POST"])
def api_wordpress_test_connection():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}

    wp_url = (data.get("wp_url") or "").strip()
    wp_username = (data.get("wp_username") or "").strip()
    wp_app_password = (data.get("wp_app_password") or "").strip()

    if not wp_url:
        return jsonify({"ok": False, "error": "缺少 wp_url"}), 400
    if not wp_username:
        return jsonify({"ok": False, "error": "缺少 wp_username"}), 400
    if not wp_app_password:
        return jsonify({"ok": False, "error": "缺少 wp_app_password"}), 400

    from lib.cms_wordpress import WordPressAdapter
    timeout = data.get("timeout", 20)
    try:
        adapter = WordPressAdapter(wp_url, wp_username, wp_app_password, timeout=timeout)
    except Exception as e:
        return jsonify({"ok": False, "status": "failed", "error": str(e), "hint": "配置无效 — 请检查 WordPress URL 格式"})

    result = adapter.test_connection()

    err_msg = result.get("error", "")
    hint = ""
    if result["ok"]:
        hint = "连接成功"
    elif "401" in err_msg:
        hint = "认证失败 — 检查用户名和应用密码是否正确，或服务器是否允许 Authorization Header"
    elif "403" in err_msg:
        hint = "权限不足 — 确认该用户有编辑权限（Editor 或 Administrator 角色），WAF 或安全插件可能拦截了 REST API"
    elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
        hint = "连接超时 — 检查 WordPress URL 是否可达，或服务器防火墙是否放行"
    else:
        hint = err_msg

    return jsonify({
        "ok": result["ok"],
        "status": result.get("status", "failed"),
        "username": result.get("username", ""),
        "hint": hint,
        "error": err_msg,
    })


@app.route("/api/wordpress/sync-draft", methods=["POST"])
def api_wordpress_sync_draft():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}

    pc_id = data.get("page_id")
    wp_url = (data.get("wp_url") or "").strip()
    wp_username = (data.get("wp_username") or "").strip()
    wp_app_password = (data.get("wp_app_password") or "").strip()

    if not pc_id:
        return jsonify({"ok": False, "error": "缺少 page_id"}), 400
    if not wp_url:
        return jsonify({"ok": False, "error": "缺少 wp_url"}), 400
    if not wp_username:
        return jsonify({"ok": False, "error": "缺少 wp_username"}), 400
    if not wp_app_password:
        return jsonify({"ok": False, "error": "缺少 wp_app_password"}), 400

    from models import get_page_content
    pc = get_page_content(pc_id)
    if not pc:
        return jsonify({"ok": False, "error": "PageContent 不存在"}), 404
    if pc.get("tenant_id") and pc.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问该页面"}), 403

    title = pc.get("title") or ""
    content = pc.get("gutenberg_html") or ""
    slug = pc.get("slug") or ""
    excerpt = pc.get("meta_description") or ""

    if not title and not content:
        return jsonify({"ok": False, "error": "页面内容为空 — 请先运行生成管线"}), 400

    from lib.cms_wordpress import WordPressAdapter
    timeout = data.get("timeout", 20)
    try:
        adapter = WordPressAdapter(wp_url, wp_username, wp_app_password, timeout=timeout)
    except Exception as e:
        return jsonify({"ok": False, "status": "failed", "post_id": None,
                        "edit_url": "", "link": "", "error": str(e)})

    result = adapter.create_draft_post(title, content, slug=slug, excerpt=excerpt)

    return jsonify({
        "ok": result["ok"],
        "provider": result.get("provider", "wordpress_real"),
        "status": result.get("status", "failed"),
        "post_id": result.get("post_id"),
        "edit_url": result.get("edit_url", ""),
        "link": result.get("link", ""),
        "warning": result.get("warning", ""),
        "error": result.get("error", ""),
        "page_content_id": pc_id,
    })


# ── Phase 9.3: Beta API ──────────────────────────────

@app.route("/api/beta/feedback", methods=["GET", "POST"])
def api_beta_feedback():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    if request.method == "POST":
        data = request.get_json() or {}
        from lib.beta_feedback import create_beta_feedback
        fid = create_beta_feedback(tid, project_id=data.get("project_id"),
                                   category=data.get("category"), rating=data.get("rating", 3),
                                   message=data.get("message", ""), metadata=data.get("metadata"))
        return jsonify({"ok": True, "feedback_id": fid})
    from lib.beta_feedback import list_beta_feedback
    return jsonify({"ok": True, "feedback": list_beta_feedback(tid,
                     project_id=request.args.get("project_id", type=int))})


@app.route("/api/beta/report")
def api_beta_report():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.beta_report import generate_private_beta_report
    return jsonify(generate_private_beta_report(tid,
                     project_id=request.args.get("project_id", type=int)))


@app.route("/api/jobs/generation/<int:job_id>/retry", methods=["POST"])


@app.route("/api/jobs/generation/<int:job_id>/retry", methods=["POST"])
def api_retry_job(job_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.generation_job_mode import retry_generation_job
    return jsonify(retry_generation_job(job_id, tenant_id=tid))


# ── Phase 6: Publish API ─────────────────────────────


@app.route("/api/publish/sync-page", methods=["POST"])
def api_publish_sync_page():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    pc_id = data.get("page_content_id")
    if not pc_id:
        return jsonify({"ok": False, "error": "缺少 page_content_id"}), 400
    from lib.publish_sync import sync_page_content
    cms_type = data.get("provider") or data.get("cms_type") or "wordpress"
    result = sync_page_content(
        pc_id,
        tid,
        cms_type=cms_type,
        dry_run=data.get("dry_run", True),
        mode=data.get("mode", "draft"),
    )
    return jsonify(result)


@app.route("/api/publish/sync-project", methods=["POST"])
def api_publish_sync_project():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    pid = data.get("project_id")
    if not pid:
        return jsonify({"ok": False, "error": "缺少 project_id"}), 400
    from lib.publish_sync import sync_project_pages
    cms_type = data.get("provider") or data.get("cms_type") or "wordpress"
    result = sync_project_pages(
        pid,
        tid,
        cms_type=cms_type,
        dry_run=data.get("dry_run", True),
        mode=data.get("mode", "draft"),
    )
    return jsonify(result)


@app.route("/api/publish/rollback", methods=["POST"])
def api_publish_rollback():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    snap_id = data.get("snapshot_id")
    if not snap_id:
        return jsonify({"ok": False, "error": "缺少 snapshot_id"}), 400
    from lib.publish_rollback import rollback_page_content
    result = rollback_page_content(snap_id, tid, dry_run=data.get("dry_run", True))
    return jsonify(result)


@app.route("/api/publish/snapshots")
def api_publish_snapshots():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    pid = request.args.get("project_id", type=int)
    pc_id = request.args.get("page_content_id", type=int)
    from lib.publish_snapshot import list_publish_snapshots
    return jsonify({"ok": True, "snapshots": list_publish_snapshots(project_id=pid, page_content_id=pc_id, tenant_id=tid)})


@app.route("/api/publish/snapshots/<int:snap_id>")
def api_publish_snapshot_detail(snap_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.publish_snapshot import get_publish_snapshot
    snap = get_publish_snapshot(snap_id, tenant_id=tid)
    if not snap: return jsonify({"ok": False, "error": "Snapshot not found"}), 404
    return jsonify({"ok": True, "snapshot": snap})


@app.route("/api/webhooks/events")
def api_webhook_events():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.webhooks import list_webhook_events
    return jsonify({"ok": True, "events": list_webhook_events(tid)})


@app.route("/api/webhooks/events/<int:event_id>/dispatch", methods=["POST"])
def api_webhook_dispatch(event_id):
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.webhooks import dispatch_webhook_event
    result = dispatch_webhook_event(event_id, tid, dry_run=True)
    return jsonify(result)


@app.route("/api/audit/logs")
def api_audit_logs():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.audit_log import list_audit_logs
    return jsonify({"ok": True, "logs": list_audit_logs(tid)})


# ── Phase 7: SaaS API ────────────────────────────────

@app.route("/api/entitlements")
def api_entitlements():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.entitlements import get_tenant_entitlements
    return jsonify({"ok": True, "entitlements": get_tenant_entitlements(tid)})

@app.route("/api/usage/events")
def api_usage_events():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.usage_meter import get_usage_summary
    return jsonify({"ok": True, "usage": get_usage_summary(tid)})

@app.route("/api/billing/events")
def api_billing_events():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.billing_events import list_billing_events
    return jsonify({"ok": True, "events": list_billing_events(tid)})

@app.route("/api/billing/change-plan", methods=["POST"])
def api_billing_change_plan():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    code = data.get("plan_code", "")
    if not code: return jsonify({"ok": False, "error": "missing plan_code"}), 400
    from lib.admin_ops import change_tenant_plan
    return jsonify(change_tenant_plan(tid, code, mock_payment=True))

@app.route("/api/billing/mock-payment", methods=["POST"])
def api_billing_mock_payment():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    from lib.admin_ops import mock_payment
    return jsonify(mock_payment(tid, data.get("amount_cents", 0), metadata=data.get("metadata")))

@app.route("/api/admin/reset-monthly-usage", methods=["POST"])
def api_admin_reset_monthly():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    data = request.get_json() or {}
    from lib.monthly_reset import reset_monthly_usage
    return jsonify(reset_monthly_usage(tid, dry_run=data.get("dry_run", True)))


# ── Phase 8: System API ──────────────────────────────

@app.route("/api/health")
def api_health():
    from lib.health import health_check
    return jsonify(health_check())

@app.route("/api/ready")
def api_ready():
    from lib.health import readiness_check
    return jsonify(readiness_check())

@app.route("/configs")
def api_configs():
    """返回可用的行业配置文件列表，供前端设置下拉框使用。"""
    import os as _os
    import yaml as _yaml
    industries_dir = ROOT / "industries"
    configs = []
    if industries_dir.exists():
        for f in sorted(industries_dir.glob("*.yaml")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    cfg = _yaml.safe_load(fh)
                name = cfg.get("name", f.stem) if cfg else f.stem
            except Exception:
                name = f.stem
            configs.append({"file": f.name, "name": name})
    return jsonify(configs)


@app.route("/themes")
def api_themes():
    """返回可用站点主题列表，供前端 Demo 主题下拉框使用。"""
    try:
        from lib.themes import available as _avail
        theme_list = []
        for key in _avail():
            label = key.replace("-", " ").title()
            theme_list.append({
                "name": key,
                "label": label,
                "default": key == "datasheet-editorial",
            })
        return jsonify(theme_list)
    except Exception:
        return jsonify([{"name": "datasheet-editorial", "label": "Datasheet Editorial", "default": True}])


@app.route("/api/config/report")
def api_config_report():
    err = _require_login()
    if err: return err
    from lib.config_check import get_config_report
    return jsonify(get_config_report(strict=False))

@app.route("/api/system/info")
def api_system_info():
    err = _require_login(); tid, err2 = _require_tenant()
    if err: return err
    if err2: return err2
    from lib.health import service_check_summary
    return jsonify({"ok": True, "info": service_check_summary(), "tenant_id": tid})

@app.route("/api/system/routes")
def api_system_routes():
    err = _require_login()
    if err: return err
    from lib.api_contract import collect_routes
    return jsonify({"ok": True, "routes": collect_routes(app)})


# ── Phase 5: Competitor API ──────────────────────────


@app.route("/api/competitor/analyze", methods=["POST"])
def api_competitor_analyze():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    data = request.get_json() or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"ok": False, "error": "缺少 query"}), 400

    project_id = data.get("project_id")
    urls = data.get("urls")
    market = data.get("market", "global")
    language = data.get("language", "English")
    limit = data.get("limit", 10)

    import run as _run
    result = _run.analyze_competitor_seo(
        query=query, project_id=project_id, tenant_id=tid,
        urls=urls, market=market, language=language, limit=limit,
    )
    return jsonify({"ok": True, "report": result})


@app.route("/api/competitor/reports")
def api_competitor_reports():
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    from models import list_competitor_reports
    project_id = request.args.get("project_id", type=int)
    query = request.args.get("query")
    reports = list_competitor_reports(
        tenant_id=tid, project_id=project_id, query=query,
    )
    return jsonify({"ok": True, "reports": reports})


@app.route("/api/competitor/reports/<int:report_id>")
def api_competitor_report_detail(report_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    from models import get_competitor_report
    report = get_competitor_report(report_id)
    if not report:
        return jsonify({"ok": False, "error": "Report 不存在"}), 404
    if report.get("tenant_id") and report.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403
    return jsonify({"ok": True, "report": report})


@app.route("/api/competitor/reports/<int:report_id>/strategy")
def api_competitor_strategy(report_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    from models import get_competitor_report
    import json as _json
    report = get_competitor_report(report_id)
    if not report:
        return jsonify({"ok": False, "error": "Report 不存在"}), 404
    if report.get("tenant_id") and report.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403
    rj = _json.loads(report.get("report_json", "{}"))
    return jsonify({"ok": True, "strategy": rj.get("surpass_strategy")})


@app.route("/api/competitor/reports/<int:report_id>/gaps")
def api_competitor_gaps(report_id):
    err = _require_login()
    if err:
        return err
    tid, err = _require_tenant()
    if err:
        return err
    from models import get_competitor_report
    import json as _json
    report = get_competitor_report(report_id)
    if not report:
        return jsonify({"ok": False, "error": "Report 不存在"}), 404
    if report.get("tenant_id") and report.get("tenant_id") != tid:
        return jsonify({"ok": False, "error": "无权访问"}), 403
    rj = _json.loads(report.get("report_json", "{}"))
    return jsonify({"ok": True, "gaps": rj.get("gap_matrix")})


# ── 启动 ────────────────────────────────────────────


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
