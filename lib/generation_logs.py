# -*- coding: utf-8 -*-
"""lib/generation_logs.py · 生成步骤日志

run.py 每个关键阶段都写日志。
页面失败必须记录具体 step 和 reason。
不允许吞异常。
"""

import json

from models import (
    create_generation_log as _create_log,
    update_generation_log as _update_log,
    list_generation_logs as _list_logs,
)


def _resolve_generation_context(generation_id: int):
    """从 generation 记录获取 tenant_id 和 project_id。"""
    if generation_id is None:
        return None, None
    try:
        from models import list_generations
        gens = list_generations()
        for g in gens:
            if g["id"] == generation_id:
                return g.get("tenant_id"), g.get("project_id")
    except Exception:
        pass
    return None, None


def log_generation_step(tenant_id: int = None, project_id: int = None,
                        generation_id: int = None, step: str = "",
                        status: str = "running", message: str = "",
                        meta: dict = None) -> int:
    """记录一个生成步骤。

    Args:
        tenant_id: 租户 ID
        project_id: 项目 ID
        generation_id: generations 表的记录 ID(单页)
        step: 步骤名称,如 "llm_generate", "quality_score", "polish", "render"
        status: "running" | "success" | "failed"
        message: 人类可读的说明
        meta: 附加上下文 dict(不抛异常,序列化失败则存 {})

    Returns:
        log 记录 id
    """
    try:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        meta_json = "{}"
    return _create_log(
        tenant_id=tenant_id,
        project_id=project_id,
        generation_id=generation_id,
        step=step,
        status=status,
        message=message,
        meta_json=meta_json,
    )


def list_generation_logs(generation_id: int = None,
                         tenant_id: int = None) -> list[dict]:
    """列出某个 generation 的所有步骤日志(按时间升序)。"""
    return _list_logs(generation_id=generation_id, tenant_id=tenant_id)


def mark_generation_failed(generation_id: int, step: str, reason: str,
                           meta: dict = None):
    """便捷函数:标记某个 generation 在某步失败。

    自动从 generation 记录解析 tenant_id 和 project_id。
    """
    if generation_id is None:
        return
    tid, pid = _resolve_generation_context(generation_id)
    log_generation_step(
        tenant_id=tid,
        project_id=pid,
        generation_id=generation_id,
        step=step,
        status="failed",
        message=reason,
        meta=meta,
    )
    # 同时更新 generations 表的状态
    try:
        from models import update_generation
        update_generation(generation_id, status="failed")
    except Exception:
        pass


def mark_generation_success(generation_id: int, meta: dict = None):
    """便捷函数:标记某个 generation 完成。

    自动从 generation 记录解析 tenant_id 和 project_id。
    如果状态已是 recovered 则保留 recovered,不覆盖为 completed。
    """
    if generation_id is None:
        return
    tid, pid = _resolve_generation_context(generation_id)
    log_generation_step(
        tenant_id=tid,
        project_id=pid,
        generation_id=generation_id,
        step="complete",
        status="success",
        message="页面生成完成",
        meta=meta,
    )
    try:
        from models import update_generation, list_generations
        # 检查当前状态:如果是 recovered,保留不覆盖
        gens = list_generations()
        current_status = "completed"
        for g in gens:
            if g["id"] == generation_id:
                current_status = g.get("status", "completed")
                break
        if current_status != "recovered":
            update_generation(generation_id, status="completed")
    except Exception:
        pass
