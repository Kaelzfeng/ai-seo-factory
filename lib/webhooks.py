# -*- coding: utf-8 -*-
"""lib/webhooks.py · Phase 6: Webhook 事件队列"""

import json


def create_webhook_event(tenant_id: int, event_type: str, payload: dict) -> int:
    from models import create_webhook_event_record
    return create_webhook_event_record(
        tenant_id=tenant_id, event_type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )


def list_webhook_events(tenant_id: int, status: str = None) -> list[dict]:
    from models import list_webhook_event_records
    return list_webhook_event_records(tenant_id=tenant_id, status=status)


def mark_webhook_event_sent(event_id: int, tenant_id: int):
    from models import update_webhook_event_status
    update_webhook_event_status(event_id, status="sent")


def mark_webhook_event_failed(event_id: int, tenant_id: int, error: str):
    from models import update_webhook_event_status
    update_webhook_event_status(event_id, status="failed", error=error)


def dispatch_webhook_event(event_id: int, tenant_id: int,
                           dry_run: bool = True) -> dict:
    """Dispatch webhook event (dry_run 默认 true)。"""
    if dry_run:
        mark_webhook_event_sent(event_id, tenant_id)
        return {"ok": True, "event_id": event_id, "status": "sent", "dry_run": True}

    # TODO: 真实 HTTP POST 到 webhook_url
    return {"ok": True, "event_id": event_id, "status": "pending",
            "dry_run": False, "note": "HTTP dispatch not implemented"}
