# -*- coding: utf-8 -*-
"""lib/admin_ops.py · Phase 7: 管理操作"""
import json
from lib.plan_catalog import get_plan_by_code, validate_plan_code


def change_tenant_plan(tenant_id: int, new_plan_code: str,
                       actor_user_id: int = None, mock_payment: bool = True) -> dict:
    """变更 tenant 套餐 (mock payment)。"""
    if not validate_plan_code(new_plan_code):
        return {"ok": False, "error": f"Invalid plan code: {new_plan_code}"}

    try:
        from models import get_active_subscription
        old_sub = get_active_subscription(tenant_id)
        old_plan = old_sub.get("plan_code", "free") if old_sub else "free"
    except Exception:
        old_plan = "free"

    plan = get_plan_by_code(new_plan_code)
    price = plan.get("price_cents", 0) if plan else 0

    # Update subscription
    try:
        from models import create_subscription
        create_subscription(tenant_id, plan_code=new_plan_code, status="active")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # Record billing event
    from lib.billing_events import record_plan_change_event, create_billing_event
    record_plan_change_event(tenant_id, old_plan, new_plan_code, actor_user_id)
    if mock_payment and price > 0:
        create_billing_event(tenant_id, "payment_mocked", amount_cents=price,
                             metadata={"plan": new_plan_code})

    # Write audit
    try:
        from lib.audit_log import create_audit_log
        create_audit_log(tenant_id, actor_user_id, "change_plan", "subscription",
                         tenant_id, {"old": old_plan, "new": new_plan_code})
    except Exception:
        pass

    return {"ok": True, "tenant_id": tenant_id, "old_plan": old_plan,
            "new_plan": new_plan_code, "price_cents": price,
            "mock_payment": mock_payment}


def mock_payment(tenant_id: int, amount_cents: int,
                 currency: str = "CNY", metadata: dict = None) -> dict:
    """Mock 支付 (不接真实平台)。"""
    from lib.billing_events import create_billing_event
    eid = create_billing_event(tenant_id, "payment_mocked",
                               amount_cents=amount_cents, currency=currency,
                               metadata=metadata)
    return {"ok": True, "tenant_id": tenant_id, "amount_cents": amount_cents,
            "billing_event_id": eid, "status": "mocked"}
