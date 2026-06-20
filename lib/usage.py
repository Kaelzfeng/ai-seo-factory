# -*- coding: utf-8 -*-
"""lib/usage.py · 用量统计薄封装

按自然月统计 generation / token 消费,供 API 和 run.py 调用。
底层数据操作在 models.py,本模块提供语义化包装 + 便捷查询。
"""

import json
import time
from models import (
    record_usage as _record_usage,
    get_monthly_usage as _get_monthly_usage,
    get_usage_summary as _get_usage_summary,
)


def record_usage(tenant_id: int, user_id: int = None, project_id: int = None,
                 kind: str = "generation", amount: int = 1,
                 meta: dict = None) -> int:
    """记录一次用量。

    Args:
        tenant_id: 租户 ID
        user_id: 触发用户(可选)
        project_id: 关联项目(可选)
        kind: generation / token
        amount: 数量
        meta: 额外元数据(dict,存为 JSON 字符串)

    Returns:
        usage_log id
    """
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    return _record_usage(tenant_id, user_id=user_id, project_id=project_id,
                         kind=kind, amount=amount, meta_json=meta_json)


def get_monthly_usage(tenant_id: int, year_month: str = None) -> dict:
    """返回指定自然月的用量汇总 dict,key 为 kind。

    Args:
        tenant_id: 租户 ID
        year_month: 'YYYY-MM' 格式,缺省当前月

    Returns:
        {"generation": 3, "token": 45000}
    """
    rows = _get_monthly_usage(tenant_id, year_month)
    return {row["kind"]: row["total"] for row in rows}


def get_usage_summary(tenant_id: int) -> dict:
    """返回当前月用量摘要(含 generation / token / 总条数)。"""
    return _get_usage_summary(tenant_id)
