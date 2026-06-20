# -*- coding: utf-8 -*-
"""lib/batch_jobs.py · 批量任务数据层 + CSV 解析

Phase 2: 支持 CSV 批量导入、批量任务创建、步骤日志。
"""

import csv
import json
import os
from pathlib import Path

from models import (
    create_batch_run as _create_batch_run,
    get_batch_run as _get_batch_run,
    list_batch_runs as _list_batch_runs,
    update_batch_run as _update_batch_run,
    create_job as _create_job,
    get_job as _get_job,
    list_jobs as _list_jobs,
    update_job as _update_job,
    create_job_step as _create_job_step,
    list_job_steps as _list_job_steps,
)


# ── CSV 解析 ──────────────────────────────────────────


def parse_batch_csv(csv_path: str) -> list[dict]:
    """解析批量 CSV 文件。

    支持字段: keyword(必填), industry_path, mode, project_id

    Args:
        csv_path: CSV 文件路径

    Returns:
        [{"keyword": str, "industry_path": str, "mode": str, "project_id": str, "_line": int}, ...]

    Raises:
        ValueError: CSV 格式错误(含行号)
    """
    if not os.path.exists(csv_path):
        raise ValueError(f"CSV 文件不存在: {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件为空或无法读取表头")

        # 检查表头
        fieldnames = [f.strip().lower() for f in reader.fieldnames]
        if "keyword" not in fieldnames:
            raise ValueError("CSV 缺少必填列: keyword")

        for line_no, raw in enumerate(reader):
            line_num = line_no + 2  # 第 1 行是表头
            row = {k.strip().lower(): v.strip() if v else "" for k, v in raw.items()}

            keyword = row.get("keyword", "")
            if not keyword:
                raise ValueError(f"第 {line_num} 行: keyword 不能为空")

            rows.append({
                "keyword": keyword,
                "industry_path": row.get("industry_path", ""),
                "mode": row.get("mode", "dry-run") or "dry-run",
                "project_id": row.get("project_id", ""),
                "_line": line_num,
            })

    if not rows:
        raise ValueError("CSV 没有有效数据行")

    return rows


# ── Batch Run CRUD ────────────────────────────────────


def create_batch_run(tenant_id: int, user_id: int = None,
                     project_id: int = None, name: str = "",
                     source: str = "", mode: str = "dry-run",
                     meta: dict = None) -> dict:
    """创建批量运行记录。"""
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    bid = _create_batch_run(
        tenant_id=tenant_id, user_id=user_id, project_id=project_id,
        name=name, source=source, mode=mode, total_jobs=0,
        meta_json=meta_json,
    )
    return _get_batch_run(bid)


def create_jobs_from_rows(batch_run_id: int, tenant_id: int,
                          user_id: int = None, project_id: int = None,
                          rows: list[dict] = None,
                          mode: str = "dry-run") -> list[dict]:
    """从 CSV 解析结果批量创建 job 记录。

    Returns:
        [job_dict, ...]
    """
    if not rows:
        return []

    jobs = []
    for row in rows:
        job_meta = {"csv_line": row.get("_line", 0)}
        meta_json = json.dumps(job_meta, ensure_ascii=False)

        jid = _create_job(
            tenant_id=tenant_id, user_id=user_id, project_id=project_id,
            batch_run_id=batch_run_id,
            keyword=row["keyword"],
            industry_path=row.get("industry_path", ""),
            mode=row.get("mode", mode),
            meta_json=meta_json,
        )
        jobs.append(_get_job(jid))

    # 更新 batch_run 的 total_jobs
    _update_batch_run(batch_run_id, total_jobs=len(jobs))

    return jobs


def get_batch_run(batch_run_id: int, tenant_id: int = None) -> dict | None:
    """获取批量运行详情。如果提供 tenant_id,校验归属。"""
    br = _get_batch_run(batch_run_id)
    if br is None:
        return None
    if tenant_id is not None and br.get("tenant_id") != tenant_id:
        return None
    return br


def list_batch_runs(tenant_id: int, limit: int = 50) -> list[dict]:
    """列出当前 tenant 的批量运行。"""
    return _list_batch_runs(tenant_id=tenant_id, limit=limit)


def list_jobs(batch_run_id: int, tenant_id: int = None,
              status: str = None) -> list[dict]:
    """列出批量运行下的任务。如果提供 tenant_id,过滤归属。"""
    if tenant_id is not None:
        # 先校验 batch_run 归属
        br = _get_batch_run(batch_run_id)
        if br is None or br.get("tenant_id") != tenant_id:
            return []
    return _list_jobs(batch_run_id=batch_run_id, tenant_id=tenant_id, status=status)


def get_job(job_id: int, tenant_id: int = None) -> dict | None:
    """获取任务详情。如果提供 tenant_id,校验归属。"""
    job = _get_job(job_id)
    if job is None:
        return None
    if tenant_id is not None and job.get("tenant_id") != tenant_id:
        return None
    return job


def update_job_status(job_id: int, status: str, **fields):
    """更新任务状态和可选字段。"""
    kwargs = {"status": status}
    kwargs.update(fields)
    _update_job(job_id, **kwargs)


def update_batch_summary(batch_run_id: int):
    """根据 jobs 表重新计算 batch_run 的统计信息。

    success 统计: completed, recovered
    failed  统计: failed
    partial 统计: partial_success, retry_pending
    忽略 retrying(正在处理中)
    """
    jobs = _list_jobs(batch_run_id=batch_run_id)
    total = len(jobs)
    success = sum(1 for j in jobs if j["status"] in ("completed", "recovered"))
    failed = sum(1 for j in jobs if j["status"] == "failed")
    partial = sum(1 for j in jobs if j["status"] in ("partial_success", "retry_pending"))

    # 确定 batch status
    if success == total:
        batch_status = "completed"
    elif success + partial == 0:
        batch_status = "failed"
    else:
        batch_status = "partial_success"

    import time
    _update_batch_run(
        batch_run_id,
        status=batch_status,
        total_jobs=total,
        success_jobs=success,
        failed_jobs=failed,
        partial_jobs=partial,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


# ── Job Step 日志 ─────────────────────────────────────


def log_job_step(job_id: int, tenant_id: int = None,
                 step: str = "", status: str = "started",
                 message: str = "", meta: dict = None) -> int:
    """记录一个 job 步骤。"""
    try:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        meta_json = "{}"
    return _create_job_step(
        job_id=job_id, tenant_id=tenant_id, step=step,
        status=status, message=message, meta_json=meta_json,
    )


def list_job_steps(job_id: int) -> list[dict]:
    """列出某个 job 的所有步骤日志(按时间升序)。"""
    return _list_job_steps(job_id)
