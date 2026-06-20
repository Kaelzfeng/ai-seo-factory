# -*- coding: utf-8 -*-
"""lib/batch_runner.py · 批量执行器

Phase 2: run_job / run_batch / retry_failed_jobs / retry_partial_jobs
"""

import json
import time

from lib.batch_jobs import (
    get_job,
    get_batch_run,
    list_jobs as _list_jobs,
    update_job_status,
    update_batch_summary,
    log_job_step,
)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def run_job(job_id: int, bypass_subscription: bool = False) -> dict:
    """执行单个 job。

    1. 读取 job
    2. 写 job_steps: started
    3. 构建 project dict,调用 run.generate_site()
    4. 更新 job 状态
    5. 写 job_steps 结果

    Returns:
        {"ok": True/False, "job_id": ..., "status": ...}
    """
    job = get_job(job_id)
    if job is None:
        return {"ok": False, "job_id": job_id, "error": "Job 不存在"}

    tenant_id = job.get("tenant_id")
    user_id = job.get("user_id")
    project_id = job.get("project_id")

    # 检查状态: 只跑 pending / retry_pending / retrying
    current_status = job.get("status", "")
    if current_status not in ("pending", "retry_pending", "retrying"):
        return {"ok": True, "job_id": job_id, "status": current_status,
                "action": "skipped", "error": f"状态为 {current_status},无需执行"}

    # ── 标记 running ──
    update_job_status(job_id, "running", started_at=_timestamp())
    log_job_step(job_id, tenant_id=tenant_id, step="job_started",
                 status="started", message=f"开始执行 job: {job.get('keyword', '')}",
                 meta={"keyword": job.get("keyword", ""),
                       "mode": job.get("mode", "dry-run")})

    try:
        # 读取行业配置
        industry_path = job.get("industry_path", "")
        industry_config = {}

        if not industry_path and project_id:
            from models import get_project
            proj = get_project(project_id)
            if proj and proj.get("industry_config"):
                industry_path = proj["industry_config"]

        if industry_path:
            import yaml
            from pathlib import Path
            if Path(industry_path).exists():
                with open(industry_path, "r", encoding="utf-8") as fh:
                    industry_config = yaml.safe_load(fh)

        # 构建 project dict
        project = {
            "id": project_id or 0,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "name": f"Batch Job: {job.get('keyword', '')}",
            "industry_config": industry_path or "",
            "seed_keyword": job.get("keyword", ""),
            "language": industry_config.get("language", "English"),
            "site_url": industry_config.get("site_url", ""),
        }

        if project_id:
            from models import get_project
            proj = get_project(project_id)
            if proj:
                project.update({
                    "wp_url": proj.get("wp_url", ""),
                    "wp_username": proj.get("wp_username", ""),
                    "wp_app_password": proj.get("wp_app_password", ""),
                })

        # ── 执行生成 ──
        import run as _run
        _run.llm.reset_usage()

        log_job_step(job_id, tenant_id=tenant_id, step="generate_site_started",
                     status="started",
                     message=f"开始 generate_site: {job.get('keyword', '')}",
                     meta={"industry_path": industry_path})

        gen_result = _run.generate_site(
            project,
            mode=job.get("mode", "dry-run"),
            bypass_subscription=bypass_subscription,
        )

        # ── 解析结果 ──
        pages_total = gen_result.get("pages_total", 0)
        pages_success = gen_result.get("pages_success", 0)
        pages_failed = gen_result.get("pages_failed", 0)
        generation_ids = gen_result.get("generation_ids", [])
        failed_gen_ids = gen_result.get("failed_generation_ids", [])
        gen_code = gen_result.get("code", "")
        gen_errors = gen_result.get("errors", [])

        meta = {
            "generation_ids": generation_ids,
            "failed_generation_ids": failed_gen_ids,
            "code": gen_code,
            "errors": gen_errors[:5],
        }

        if gen_code == "success":
            update_job_status(
                job_id, "completed",
                pages_total=pages_total,
                pages_success=pages_success,
                pages_failed=0,
                generation_id=generation_ids[0] if generation_ids else None,
                retryable=0,
                finished_at=_timestamp(),
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
            log_job_step(job_id, tenant_id=tenant_id,
                         step="generate_site_finished",
                         status="success",
                         message=f"generate_site 成功: {pages_success}/{pages_total}",
                         meta=meta)
            log_job_step(job_id, tenant_id=tenant_id, step="job_completed",
                         status="success",
                         message=f"{pages_success}/{pages_total} pages generated",
                         meta=meta)

        elif gen_code == "partial_success":
            update_job_status(
                job_id, "partial_success",
                pages_total=pages_total,
                pages_success=pages_success,
                pages_failed=pages_failed,
                generation_id=generation_ids[0] if generation_ids else None,
                retryable=1,
                finished_at=_timestamp(),
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
            log_job_step(job_id, tenant_id=tenant_id,
                         step="generate_site_finished",
                         status="failed",
                         message=f"generate_site 部分成功: {pages_success}/{pages_total}",
                         meta=meta)
            log_job_step(job_id, tenant_id=tenant_id, step="job_partial",
                         status="failed",
                         message=f"{pages_success}/{pages_total} pages (partial)",
                         meta=meta)

        else:
            update_job_status(
                job_id, "failed",
                pages_total=pages_total,
                pages_success=0,
                pages_failed=pages_total or 1,
                retryable=1 if failed_gen_ids else 0,
                error=gen_errors[0] if gen_errors else "Generation failed",
                finished_at=_timestamp(),
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
            log_job_step(job_id, tenant_id=tenant_id,
                         step="generate_site_failed",
                         status="failed",
                         message=gen_errors[0] if gen_errors else "Generation failed",
                         meta=meta)
            log_job_step(job_id, tenant_id=tenant_id, step="job_failed",
                         status="failed",
                         message=gen_errors[0] if gen_errors else "Generation failed",
                         meta=meta)

        return {
            "ok": gen_code in ("success", "partial_success"),
            "job_id": job_id,
            "status": gen_code,
            "pages_success": pages_success,
            "pages_total": pages_total,
        }

    except Exception as e:
        # ── 异常处理 ──
        update_job_status(
            job_id, "failed",
            error=str(e),
            retryable=1,
            finished_at=_timestamp(),
        )
        log_job_step(job_id, tenant_id=tenant_id, step="job_error",
                     status="failed", message=str(e))
        return {"ok": False, "job_id": job_id, "error": str(e)}


def run_batch(batch_run_id: int, bypass_subscription: bool = False,
              max_jobs: int = None) -> dict:
    """执行整个批量运行。

    1. 读取 batch_run
    2. 状态改 running
    3. 逐个执行 pending / retry_pending job
    4. 每个 job 失败不中断 batch
    5. 执行完更新 batch summary

    Returns:
        {"ok": bool, "batch_run_id": ..., "results": [...], "summary": {...}}
    """
    br = get_batch_run(batch_run_id)
    if br is None:
        return {"ok": False, "error": "Batch run 不存在"}

    # 标记 running
    from models import update_batch_run
    update_batch_run(batch_run_id, status="running", started_at=_timestamp())

    # 获取待执行 jobs
    jobs = _list_jobs(batch_run_id=batch_run_id)
    todo = [j for j in jobs if j["status"] in ("pending", "retry_pending")]
    if max_jobs:
        todo = todo[:max_jobs]

    results = []
    for idx, job in enumerate(todo):
        print(f"  [{idx+1}/{len(todo)}] Job {job['id']}: {job.get('keyword', '')} ... ", end="", flush=True)
        res = run_job(job["id"], bypass_subscription=bypass_subscription)
        status = res.get("status", "error")
        pages = f"{res.get('pages_success', 0)}/{res.get('pages_total', 0)}"
        print(f"{status} ({pages} pages)")
        results.append(res)

    # 更新 batch summary
    update_batch_summary(batch_run_id)

    # 最终状态
    br_final = get_batch_run(batch_run_id)
    return {
        "ok": len([r for r in results if r.get("ok")]) > 0,
        "batch_run_id": batch_run_id,
        "results": results,
        "summary": {
            "total": br_final.get("total_jobs", 0) if br_final else len(todo),
            "success": br_final.get("success_jobs", 0) if br_final else 0,
            "failed": br_final.get("failed_jobs", 0) if br_final else 0,
            "partial": br_final.get("partial_jobs", 0) if br_final else 0,
            "status": br_final.get("status", "unknown") if br_final else "unknown",
        },
    }


def retry_failed_jobs(batch_run_id: int,
                      bypass_subscription: bool = False) -> dict:
    """重跑 batch 中所有失败/partial/retry_pending job。

    不重跑 completed job。
    重跑前写 retrying,成功后写 recovered/completed。
    """
    br = get_batch_run(batch_run_id)
    if br is None:
        return {"ok": False, "error": "Batch run 不存在"}

    from models import update_batch_run
    update_batch_run(batch_run_id, status="retrying")

    jobs = _list_jobs(batch_run_id=batch_run_id)
    retryable = [j for j in jobs
                 if j["status"] in ("failed", "partial_success", "retry_pending")]

    results = []
    for job in retryable:
        # 标记 retrying
        update_job_status(job["id"], "retrying")
        tenant_id = job.get("tenant_id")
        log_job_step(job["id"], tenant_id=tenant_id, step="retry_started",
                     status="started", message="开始重试")

        res = run_job(job["id"], bypass_subscription=bypass_subscription)

        if res.get("status") == "success":
            # 改为 recovered 而非 completed,表示是补跑成功的
            update_job_status(job["id"], "recovered")
            log_job_step(job["id"], tenant_id=tenant_id, step="retry_recovered",
                         status="success", message="补跑成功")
        results.append(res)

    update_batch_summary(batch_run_id)
    br_final = get_batch_run(batch_run_id)

    return {
        "ok": True,
        "batch_run_id": batch_run_id,
        "results": results,
        "summary": {
            "total": br_final.get("total_jobs", 0) if br_final else 0,
            "success": br_final.get("success_jobs", 0) if br_final else 0,
            "failed": br_final.get("failed_jobs", 0) if br_final else 0,
            "partial": br_final.get("partial_jobs", 0) if br_final else 0,
            "status": br_final.get("status", "unknown") if br_final else "unknown",
        },
    }


def retry_partial_jobs(batch_run_id: int,
                       bypass_subscription: bool = False) -> dict:
    """对 partial_success job 调用 retry_failed_pages 补跑失败页。

    不重复生成已成功页面。
    补跑成功后 job 状态改 recovered。
    """
    br = get_batch_run(batch_run_id)
    if br is None:
        return {"ok": False, "error": "Batch run 不存在"}

    from models import update_batch_run
    update_batch_run(batch_run_id, status="retrying")

    jobs = _list_jobs(batch_run_id=batch_run_id)
    partial_jobs = [j for j in jobs if j["status"] in ("partial_success", "retry_pending")]

    results = []
    for job in partial_jobs:
        tenant_id = job.get("tenant_id")
        project_id = job.get("project_id")

        log_job_step(job["id"], tenant_id=tenant_id, step="retry_partial_started",
                     status="started", message="开始补跑失败页")

        # 解析 meta 中的 failed_generation_ids
        meta_str = job.get("meta_json", "{}")
        try:
            meta = json.loads(meta_str)
        except (json.JSONDecodeError, TypeError):
            meta = {}
        failed_gen_ids = meta.get("failed_generation_ids", [])

        if not failed_gen_ids:
            # 没有可补跑的 generation
            results.append({
                "ok": True, "job_id": job["id"], "action": "skipped",
                "error": "没有可补跑的失败页",
            })
            log_job_step(job["id"], tenant_id=tenant_id, step="retry_partial_skipped",
                         status="skipped", message="没有可补跑的失败页")
            continue

        # 构建 project dict
        project = {
            "id": project_id or 0,
            "tenant_id": tenant_id,
            "user_id": job.get("user_id"),
            "name": f"Retry: {job.get('keyword', '')}",
            "industry_config": job.get("industry_path", ""),
            "seed_keyword": job.get("keyword", ""),
        }

        if project_id:
            from models import get_project
            proj = get_project(project_id)
            if proj:
                project.update({
                    "wp_url": proj.get("wp_url", ""),
                    "wp_username": proj.get("wp_username", ""),
                    "wp_app_password": proj.get("wp_app_password", ""),
                })

        # 调用 retry_failed_pages
        try:
            import run as _run
            _run.llm.reset_usage()

            from lib.retry_pages import retry_failed_pages
            retry_result = retry_failed_pages(
                project=project,
                project_id=project_id,
                generation_ids=failed_gen_ids,
                mode=job.get("mode", "dry-run"),
                bypass_subscription=bypass_subscription,
            )

            if retry_result["summary"]["recovered"] > 0:
                # 重新统计
                success_pages = job.get("pages_success", 0) + retry_result["summary"]["recovered"]
                failed_pages = job.get("pages_failed", 0) - retry_result["summary"]["recovered"]

                if failed_pages == 0:
                    update_job_status(job["id"], "recovered",
                                     pages_success=success_pages, pages_failed=0,
                                     retryable=0)
                    log_job_step(job["id"], tenant_id=tenant_id,
                                 step="retry_partial_recovered",
                                 status="success",
                                 message=f"补跑成功: {retry_result['summary']['recovered']} pages recovered")
                else:
                    update_job_status(job["id"], "partial_success",
                                     pages_success=success_pages,
                                     pages_failed=failed_pages)

            results.append({
                "ok": True, "job_id": job["id"],
                "retry_summary": retry_result["summary"],
            })

        except Exception as e:
            log_job_step(job["id"], tenant_id=tenant_id, step="retry_partial_error",
                         status="failed", message=str(e))
            results.append({
                "ok": False, "job_id": job["id"], "error": str(e),
            })

    update_batch_summary(batch_run_id)
    br_final = get_batch_run(batch_run_id)

    return {
        "ok": True,
        "batch_run_id": batch_run_id,
        "results": results,
        "summary": {
            "total": br_final.get("total_jobs", 0) if br_final else 0,
            "success": br_final.get("success_jobs", 0) if br_final else 0,
            "failed": br_final.get("failed_jobs", 0) if br_final else 0,
            "partial": br_final.get("partial_jobs", 0) if br_final else 0,
            "status": br_final.get("status", "unknown") if br_final else "unknown",
        },
    }
