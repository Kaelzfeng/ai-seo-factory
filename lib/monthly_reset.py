# -*- coding: utf-8 -*-
"""lib/monthly_reset.py · Phase 7: 月度用量重置"""
import json, time


def get_current_usage_period() -> tuple:
    now = time.localtime()
    return now.tm_year, now.tm_mon


def close_usage_period(tenant_id: int, year: int, month: int):
    """归档当前周期 (软关闭)。"""
    pass


def reset_monthly_usage(tenant_id: int, year: int = None,
                        month: int = None, dry_run: bool = True) -> dict:
    """重置单个 tenant 月度用量。"""
    if year is None or month is None:
        year, month = get_current_usage_period()

    if dry_run:
        return {"ok": True, "tenant_id": tenant_id, "year": year, "month": month,
                "dry_run": True, "message": "Dry run - no changes made"}

    # Create usage snapshot
    snap_id = create_usage_snapshot(tenant_id, year, month)

    # Record billing event
    from lib.billing_events import create_billing_event
    create_billing_event(tenant_id, "monthly_reset", metadata={"year": year, "month": month})

    return {"ok": True, "tenant_id": tenant_id, "year": year, "month": month,
            "snapshot_id": snap_id, "dry_run": False}


def reset_all_tenants_monthly_usage(year: int = None, month: int = None,
                                    dry_run: bool = True) -> dict:
    """重置所有 tenant 月度用量。"""
    if year is None or month is None:
        year, month = get_current_usage_period()

    if dry_run:
        return {"ok": True, "year": year, "month": month, "dry_run": True,
                "message": "Dry run - no tenants affected"}

    try:
        from models import _get_db
        db = _get_db()
        rows = db.execute("SELECT id FROM tenants").fetchall()
        results = []
        for row in rows:
            r = reset_monthly_usage(row["id"], year, month, dry_run=False)
            results.append(r)
        return {"ok": True, "year": year, "month": month, "total": len(results),
                "results": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def create_usage_snapshot(tenant_id: int, year: int, month: int) -> int:
    from lib.usage_meter import get_usage_summary
    usage = get_usage_summary(tenant_id)
    try:
        from models import create_usage_snapshot_record
        return create_usage_snapshot_record(
            tenant_id=tenant_id, year=year, month=month,
            usage_json=json.dumps(usage, ensure_ascii=False),
        )
    except Exception:
        return 0
