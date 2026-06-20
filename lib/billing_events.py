# -*- coding: utf-8 -*-
"""lib/billing_events.py · Phase 7: 账单事件"""
import json


def create_billing_event(tenant_id: int, event_type: str,
                         amount_cents: int = 0, currency: str = "CNY",
                         metadata: dict = None) -> int:
    try:
        from models import create_billing_event_record
        return create_billing_event_record(
            tenant_id=tenant_id, event_type=event_type,
            amount_cents=amount_cents, currency=currency,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
    except Exception:
        return 0


def list_billing_events(tenant_id: int, event_type: str = None) -> list[dict]:
    try:
        from models import list_billing_event_records
        return list_billing_event_records(tenant_id=tenant_id, event_type=event_type)
    except Exception:
        return []


def mark_billing_event_processed(event_id: int, tenant_id: int):
    try:
        from models import update_billing_event_status
        update_billing_event_status(event_id, status="processed")
    except Exception:
        pass


def mark_billing_event_failed(event_id: int, tenant_id: int, error: str):
    try:
        from models import update_billing_event_status
        update_billing_event_status(event_id, status="failed", error=error)
    except Exception:
        pass


def record_plan_change_event(tenant_id: int, old_plan: str, new_plan: str,
                             actor_user_id: int = None):
    return create_billing_event(tenant_id, "plan_changed", metadata={
        "old_plan": old_plan, "new_plan": new_plan, "actor": actor_user_id,
    })


def record_quota_exceeded_event(tenant_id: int, kind: str, limit: int, used: int):
    return create_billing_event(tenant_id, "quota_exceeded", metadata={
        "kind": kind, "limit": limit, "used": used,
    })
