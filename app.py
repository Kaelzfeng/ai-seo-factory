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


@app.route("/projects")
def projects():
    from auth import current_user, current_tenant_id, login_required as _lr

    user = current_user()
    if not user:
        return redirect(url_for("login"))

    tid = current_tenant_id()
    from models import list_projects as _list_projects
    proj_list = _list_projects(tenant_id=tid) if tid else []

    ctx = _get_template_context(projects=proj_list)
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


@app.route("/run", methods=["POST"])
def run_generate():
    from auth import current_user, current_tenant_id
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "未登录"}), 401

    data = request.get_json() or {}
    project_id = data.get("project_id")
    mode = data.get("mode", "dry-run")

    from models import get_project
    proj = get_project(project_id) if project_id else None
    if not proj:
        return jsonify({"ok": False, "error": "项目不存在"}), 404

    # 确保 project 有 tenant_id
    tid = current_tenant_id()
    if not proj.get("tenant_id"):
        proj["tenant_id"] = tid
    if not proj.get("user_id"):
        proj["user_id"] = user["id"]

    import run as _run
    _run.llm.reset_usage()

    result = _run.generate_site(proj, mode=mode)
    return jsonify(result)


@app.route("/demo")
def demo():
    """演示页面 —— 显示 output_src/ 中最新渲染结果。"""
    from auth import current_user
    outdir = ROOT / "output_src"
    files = sorted(outdir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True) if outdir.exists() else []
    ctx = _get_template_context(demo_files=[f.name for f in files[:10]], user=current_user())
    return render_template("index.html", **ctx)


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
    result = sync_page_content(pc_id, tid, dry_run=data.get("dry_run", True), mode=data.get("mode", "draft"))
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
    result = sync_project_pages(pid, tid, dry_run=data.get("dry_run", True), mode=data.get("mode", "draft"))
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
    reports = list_competitor_reports(tenant_id=tid)
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
