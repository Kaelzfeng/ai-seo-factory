# -*- coding: utf-8 -*-
"""lib/entitlements.py · Phase 7: 权限判断引擎"""
import time
from lib.plan_catalog import get_plan_by_code
from lib.usage_meter import get_usage_summary as _get_usage


def _get_active_plan(tenant_id: int) -> dict:
    try:
        from models import get_active_subscription
        sub = get_active_subscription(tenant_id)
        if sub:
            code = sub.get("plan_code", "free")
            plan = get_plan_by_code(code) or get_plan_by_code("free")
            plan["_subscription"] = sub
            return plan
    except Exception:
        pass
    return get_plan_by_code("free") or {}


def get_tenant_entitlements(tenant_id: int) -> dict:
    plan = _get_active_plan(tenant_id)
    usage = _get_usage(tenant_id)
    return {
        "plan_code": plan.get("code", "free"),
        "plan_name": plan.get("name", "Free"),
        "subscription_status": plan.get("_subscription", {}).get("status", "active"),
        "limits": {
            "generation": plan.get("monthly_generation_limit", 3),
            "token": plan.get("monthly_token_limit", 100000),
            "competitor_analysis": plan.get("monthly_competitor_analysis_limit", 1),
            "publish_sync": plan.get("monthly_publish_sync_limit", 3),
            "batch_jobs": plan.get("max_batch_jobs", 0),
            "projects": plan.get("max_projects", 1),
            "sites": plan.get("max_sites", 1),
            "blueprint_pages": plan.get("max_pages_per_blueprint", 8),
        },
        "usage": usage,
    }


def get_current_plan(tenant_id: int) -> dict:
    return _get_active_plan(tenant_id)


def _check_limit(tenant_id: int, kind: str, amount: int = 1) -> dict:
    ent = get_tenant_entitlements(tenant_id)
    limit = ent["limits"].get(kind, 0)
    used = ent["usage"].get(kind, 0)
    remaining = max(0, limit - used)
    ok = (used + amount) <= limit if limit > 0 else True
    reason = None if ok else f"monthly_{kind}_limit_reached"
    return {"ok": ok, "kind": kind, "limit": limit, "used": used,
            "remaining": remaining, "plan_code": ent["plan_code"], "reason": reason}


def can_create_project(tenant_id: int) -> dict:
    try:
        from models import list_projects
        projects = list_projects(tenant_id=tenant_id)
        ent = get_tenant_entitlements(tenant_id)
        limit = ent["limits"]["projects"]
        ok = len(projects) < limit
        return {"ok": ok, "kind": "projects", "limit": limit, "used": len(projects),
                "remaining": max(0, limit - len(projects)), "plan_code": ent["plan_code"],
                "reason": None if ok else "max_projects_reached"}
    except Exception:
        return {"ok": True, "reason": None}


def can_add_site(tenant_id: int) -> dict:
    return _check_limit(tenant_id, "sites")


def can_generate_content(tenant_id: int, amount: int = 1) -> dict:
    return _check_limit(tenant_id, "generation", amount)


def can_run_competitor_analysis(tenant_id: int, amount: int = 1) -> dict:
    return _check_limit(tenant_id, "competitor_analysis", amount)


def can_sync_publish(tenant_id: int, amount: int = 1) -> dict:
    return _check_limit(tenant_id, "publish_sync", amount)


def can_run_batch_jobs(tenant_id: int, amount: int = 1) -> dict:
    return _check_limit(tenant_id, "batch_jobs", amount)


def can_create_blueprint_pages(tenant_id: int, pages_count: int) -> dict:
    ent = get_tenant_entitlements(tenant_id)
    limit = ent["limits"]["blueprint_pages"]
    ok = pages_count <= limit
    return {"ok": ok, "kind": "blueprint_pages", "limit": limit, "used": pages_count,
            "remaining": max(0, limit - pages_count), "plan_code": ent["plan_code"],
            "reason": None if ok else "max_blueprint_pages_exceeded"}


def explain_limit_denial(kind: str, entitlement: dict, current_usage: dict) -> str:
    return f"{kind} limit reached: {current_usage.get(kind, 0)}/{entitlement['limits'].get(kind, 0)}"
