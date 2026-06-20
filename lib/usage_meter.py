# -*- coding: utf-8 -*-
"""lib/usage_meter.py · Phase 7: 用量记录 + 聚合"""
import json, time


def record_usage_event(tenant_id: int, event_type: str, amount: int = 1,
                       metadata: dict = None) -> int:
    from models import record_usage
    meta = json.dumps(metadata or {}, ensure_ascii=False)
    return record_usage(tenant_id, kind=event_type, amount=amount, meta_json=meta)


def get_usage_summary(tenant_id: int, period: str = None) -> dict:
    from models import get_monthly_usage
    monthly = get_monthly_usage(tenant_id)
    result = {}
    for row in monthly:
        result[row["kind"]] = row["total"]
    return result


def get_usage_by_event_type(tenant_id: int, event_type: str,
                            period: str = None) -> int:
    summary = get_usage_summary(tenant_id, period)
    return summary.get(event_type, 0)


def get_monthly_usage(tenant_id: int, year: int = None,
                      month: int = None) -> dict:
    summary = get_usage_summary(tenant_id)
    return summary


def get_remaining_quota(tenant_id: int) -> dict:
    from lib.entitlements import get_tenant_entitlements
    ent = get_tenant_entitlements(tenant_id)
    remaining = {}
    for kind, limit in ent["limits"].items():
        used = ent["usage"].get(kind, 0)
        remaining[kind] = max(0, limit - used)
    return remaining


def estimate_operation_cost(operation_type: str, payload: dict = None) -> dict:
    estimates = {
        "generation": {"tokens": 5000, "api_calls": 1},
        "competitor_analysis": {"tokens": 2000, "api_calls": 1},
        "publish_sync": {"tokens": 0, "api_calls": 1},
        "batch_job": {"tokens": 5000, "api_calls": 1},
    }
    return estimates.get(operation_type, {"tokens": 0, "api_calls": 0})
