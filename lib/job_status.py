# -*- coding: utf-8 -*-
"""lib/job_status.py · Phase 9.2: Job 状态查询辅助"""
from lib.generation_job_mode import get_generation_job_status, get_generation_job_result


def format_job_status(job_id: int, tenant_id: int = None) -> str:
    """格式化 job 状态为可读字符串。"""
    s = get_generation_job_status(job_id, tenant_id)
    if not s.get("ok"):
        return f"Job {job_id}: not found"
    return (f"Job {job_id}: {s['status']} "
            f"({s.get('pages_success', 0)}/{s.get('pages_total', 0)} pages) "
            f"last_step={s.get('last_step', 'N/A')}")


def is_job_terminal(job_id: int, tenant_id: int = None) -> bool:
    s = get_generation_job_status(job_id, tenant_id)
    return s.get("status") in ("completed", "failed", "cancelled", "partial_success")
