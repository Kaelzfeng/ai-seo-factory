# -*- coding: utf-8 -*-
"""lib/generation_job_mode.py · Phase 9.2: 异步生成 Job Mode

复用 batch_runs/jobs/job_steps 表, 把单次生成包装成 batch_run(1 job)。
支持 create / run / status / result / cancel / retry。
"""

import json
import threading
import time

# ── Create ───────────────────────────────────────────


def create_generation_job(tenant_id: int, project_id: int = None,
                          user_input: str = None,
                          blueprint_id: int = None,
                          mode: str = "dry-run",
                          use_competitor: bool = False,
                          competitor_query: str = None,
                          bypass_subscription: bool = False,
                          metadata: dict = None) -> dict:
    """创建生成任务 (queued 状态, 不执行)。"""
    from models import create_batch_run, create_job, update_batch_run

    # Create a "virtual" batch_run for this single job
    bid = create_batch_run(
        tenant_id=tenant_id, user_id=None, project_id=project_id,
        name=f"gen-job-{int(time.time())}", source="generation_job",
        mode=mode, total_jobs=1,
    )

    # Build input
    input_data = {
        "user_input": user_input,
        "blueprint_id": blueprint_id,
        "mode": mode,
        "use_competitor": use_competitor,
        "competitor_query": competitor_query,
        "bypass_subscription": bypass_subscription,
    }
    meta = dict(metadata or {})
    meta["_input"] = input_data

    jid = create_job(
        tenant_id=tenant_id, batch_run_id=bid,
        keyword=user_input[:80] if user_input else "generation",
        project_id=project_id, mode=mode,
        meta_json=json.dumps(meta, ensure_ascii=False),
    )

    # Log step
    from lib.batch_jobs import log_job_step
    log_job_step(jid, tenant_id=tenant_id, step="job_created",
                 status="started", message="Generation job created",
                 meta={"user_input": user_input, "mode": mode})

    return {"ok": True, "job_id": jid, "batch_run_id": bid, "status": "queued"}


# ── Run ─────────────────────────────────────────────


def run_generation_job(job_id: int, tenant_id: int = None) -> dict:
    """同步执行生成任务。"""
    job = _get_job(job_id, tenant_id)
    if job is None:
        return {"ok": False, "error": "Job not found or tenant mismatch"}

    _transition_status(job_id, "running", tenant_id)
    _log_step(job_id, tenant_id, "job_started", "Generation job started")

    try:
        # Parse input
        meta = _parse_meta(job)
        inp = meta.get("_input", {})
        user_input = inp.get("user_input", "")
        blueprint_id = inp.get("blueprint_id")
        mode = inp.get("mode", "dry-run")
        use_competitor = inp.get("use_competitor", False)
        competitor_query = inp.get("competitor_query")
        bypass = inp.get("bypass_subscription", False)

        import run as _run
        _run.llm.reset_usage()

        if blueprint_id:
            # Generate from existing blueprint
            _log_step(job_id, tenant_id, "blueprint_loaded", f"Using blueprint {blueprint_id}")
            from models import get_site_blueprint
            bp_row = get_site_blueprint(blueprint_id)
            if bp_row:
                import json as _json
                from lib.seo_engine.schemas import SiteBlueprint
                bp = SiteBlueprint.from_dict(_json.loads(bp_row["blueprint_json"]))
                result = _run.generate_site_from_blueprint(
                    {"id": job.get("project_id", 0), "tenant_id": tenant_id,
                     "user_id": job.get("user_id"), "name": "Job Gen"},
                    bp, mode=mode, bypass_subscription=bypass,
                )
            else:
                return {"ok": False, "error": "Blueprint not found"}
        elif user_input:
            # Full pipeline from input
            _log_step(job_id, tenant_id, "clarify_started", "Starting S0 clarify")
            result = _run.generate_site_from_input(
                user_input, project_id=job.get("project_id"),
                tenant_id=tenant_id, mode=mode, bypass_subscription=bypass,
                use_competitor=use_competitor, competitor_query=competitor_query,
            )
        else:
            return {"ok": False, "error": "No user_input or blueprint_id provided"}

        # Update job with result
        _update_result(job_id, result, tenant_id)
        return {"ok": True, "job_id": job_id, "status": result.get("code", "completed"),
                "result": result}

    except Exception as e:
        _transition_status(job_id, "failed", tenant_id)
        _log_step(job_id, tenant_id, "job_failed", str(e))
        error_json = json.dumps({"error": str(e), "type": type(e).__name__}, ensure_ascii=False)
        _update_error(job_id, error_json)
        return {"ok": False, "job_id": job_id, "status": "failed", "error": str(e)}


def run_generation_job_background(job_id: int, tenant_id: int = None) -> dict:
    """后台线程执行生成任务。"""
    t = threading.Thread(target=run_generation_job, args=(job_id, tenant_id), daemon=True)
    t.start()
    return {"ok": True, "job_id": job_id, "status": "running", "background": True}


# ── Status / Result ─────────────────────────────────


def get_generation_job_status(job_id: int, tenant_id: int = None) -> dict:
    job = _get_job(job_id, tenant_id)
    if job is None:
        return {"ok": False, "error": "Job not found"}
    steps = _get_steps(job_id)
    return {
        "ok": True, "job_id": job_id,
        "status": job.get("status", "unknown"),
        "pages_success": job.get("pages_success", 0),
        "pages_total": job.get("pages_total", 0),
        "pages_failed": job.get("pages_failed", 0),
        "created_at": job.get("created_at", ""),
        "started_at": job.get("started_at", ""),
        "finished_at": job.get("finished_at", ""),
        "last_step": steps[-1]["step"] if steps else None,
        "error": job.get("error", ""),
    }


def get_generation_job_result(job_id: int, tenant_id: int = None) -> dict:
    job = _get_job(job_id, tenant_id)
    if job is None:
        return {"ok": False, "error": "Job not found"}
    meta = _parse_meta(job)
    return {"ok": True, "job_id": job_id, "status": job.get("status"),
            "pages_success": job.get("pages_success"),
            "pages_total": job.get("pages_total"),
            "result": meta.get("_result")}


# ── Cancel / Retry ──────────────────────────────────


def cancel_generation_job(job_id: int, tenant_id: int = None) -> dict:
    job = _get_job(job_id, tenant_id)
    if job is None:
        return {"ok": False, "error": "Job not found"}
    status = job.get("status", "")
    if status in ("queued", "pending"):
        _transition_status(job_id, "cancelled", tenant_id)
        _log_step(job_id, tenant_id, "job_cancelled", "Cancelled by user")
        return {"ok": True, "job_id": job_id, "status": "cancelled"}
    elif status == "running":
        _log_step(job_id, tenant_id, "cancel_requested", "Cancel requested (not force-killed)")
        return {"ok": True, "job_id": job_id, "status": "running",
                "note": "Cancel requested, but running jobs cannot be force-killed"}
    return {"ok": False, "error": f"Cannot cancel job in status: {status}"}


def retry_generation_job(job_id: int, tenant_id: int = None) -> dict:
    job = _get_job(job_id, tenant_id)
    if job is None:
        return {"ok": False, "error": "Job not found"}
    status = job.get("status", "")
    if status in ("failed", "partial_success"):
        _transition_status(job_id, "queued", tenant_id)
        _log_step(job_id, tenant_id, "job_retry_queued", "Re-queued for retry")
        return {"ok": True, "job_id": job_id, "status": "queued"}
    return {"ok": False, "error": f"Cannot retry job in status: {status}"}


# ── Helpers ─────────────────────────────────────────


def _get_job(job_id: int, tenant_id: int = None):
    try:
        from models import get_job
        job = get_job(job_id)
        if job and tenant_id is not None and job.get("tenant_id") != tenant_id:
            return None
        return job
    except Exception:
        return None


def _get_steps(job_id: int) -> list:
    try:
        from lib.batch_jobs import list_job_steps
        return list_job_steps(job_id)
    except Exception:
        return []


def _transition_status(job_id: int, status: str, tenant_id: int = None):
    try:
        from models import update_job
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        kwargs = {"status": status}
        if status == "running":
            kwargs["started_at"] = now
        if status in ("completed", "failed", "cancelled"):
            kwargs["finished_at"] = now
        update_job(job_id, **kwargs)
    except Exception:
        pass


def _log_step(job_id: int, tenant_id: int, step: str, message: str, meta: dict = None):
    try:
        from lib.batch_jobs import log_job_step
        log_job_step(job_id, tenant_id=tenant_id, step=step, status="started",
                     message=message, meta=meta)
    except Exception:
        pass


def _parse_meta(job: dict) -> dict:
    try:
        return json.loads(job.get("meta_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}


def _update_result(job_id: int, result: dict, tenant_id: int = None):
    job = _get_job(job_id, tenant_id)
    if not job:
        return
    meta = _parse_meta(job)
    meta["_result"] = {
        "code": result.get("code"),
        "pages_total": result.get("pages_total"),
        "pages_success": result.get("pages_success"),
        "pages_failed": result.get("pages_failed"),
        "generation_ids": result.get("generation_ids"),
    }
    from models import update_job
    status = "completed" if result.get("code") == "success" else \
             "partial_success" if result.get("pages_success", 0) > 0 else "failed"
    update_job(job_id, status=status,
               pages_total=result.get("pages_total", 0),
               pages_success=result.get("pages_success", 0),
               pages_failed=result.get("pages_failed", 0),
               finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
               meta_json=json.dumps(meta, ensure_ascii=False))
    _log_step(job_id, tenant_id, "job_completed",
              f"{result.get('pages_success', 0)}/{result.get('pages_total', 0)} pages")


def _update_error(job_id: int, error_json: str):
    try:
        from models import update_job
        update_job(job_id, error=error_json)
    except Exception:
        pass
