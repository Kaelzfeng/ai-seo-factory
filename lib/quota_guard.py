# -*- coding: utf-8 -*-
"""lib/quota_guard.py · Phase 7: 额度守卫"""

_OP_MAP = {
    "generate_site_from_input": "generation",
    "generate_site_from_blueprint": "generation",
    "analyze_competitor_seo": "competitor_analysis",
    "sync_page_content": "publish_sync",
    "sync_project_pages": "publish_sync",
    "run_batch": "batch_job",
    "rollback_page_content": "rollback",
    "blueprint_page": "blueprint_pages",
}


def check_quota(tenant_id: int, operation_type: str,
                amount: int = 1) -> dict:
    kind = _OP_MAP.get(operation_type, operation_type)
    from lib.entitlements import _check_limit
    return _check_limit(tenant_id, kind, amount)


def check_quota_or_raise(tenant_id: int, operation_type: str,
                         amount: int = 1):
    r = check_quota(tenant_id, operation_type, amount)
    if not r["ok"]:
        from lib.entitlements import explain_limit_denial
        msg = explain_limit_denial(r["kind"], {}, {r["kind"]: r["used"]})
        raise QuotaExceededError(msg, r)
    return r


def consume_quota(tenant_id: int, operation_type: str,
                  amount: int = 1, metadata: dict = None):
    kind = _OP_MAP.get(operation_type, operation_type)
    from lib.usage_meter import record_usage_event
    return record_usage_event(tenant_id, kind, amount, metadata)


def guarded_operation(tenant_id: int, operation_type: str,
                      amount: int = 1,
                      bypass_subscription: bool = False,
                      dry_run: bool = False) -> dict:
    if bypass_subscription or dry_run:
        return {"ok": True, "bypassed": True, "kind": operation_type, "guarded": False}
    ck = check_quota(tenant_id, operation_type, amount)
    if not ck["ok"]:
        return {"ok": False, "code": "quota_exceeded", **ck}
    consume_quota(tenant_id, operation_type, amount)
    return {"ok": True, "kind": ck["kind"], "consumed": amount, "guarded": True}


class QuotaExceededError(Exception):
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
