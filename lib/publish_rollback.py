# -*- coding: utf-8 -*-
"""lib/publish_rollback.py · Phase 6: 发布回滚

从快照恢复 CMS 内容。
"""

from lib.cms_adapter import get_cms_adapter
from lib.publish_snapshot import get_publish_snapshot, snapshot_to_restore_payload


def rollback_page_content(snapshot_id: int, tenant_id: int,
                          dry_run: bool = False) -> dict:
    """回滚到指定快照。"""
    snap = get_publish_snapshot(snapshot_id, tenant_id=tenant_id)
    if snap is None:
        return {"ok": False, "status": "failed", "snapshot_id": snapshot_id,
                "errors": ["Snapshot not found or tenant mismatch"]}

    payload = snapshot_to_restore_payload(snap)
    remote_id = snap.get("remote_id", "")

    if dry_run:
        return {"ok": True, "status": "dry_run", "snapshot_id": snapshot_id,
                "remote_id": remote_id, "restore_payload": payload, "errors": []}

    # Execute rollback
    adapter = get_cms_adapter()
    result = adapter.update_content(remote_id, payload)

    # Write cms_log
    try:
        from lib.cms_logs import record_cms_log
        record_cms_log(tenant_id=tenant_id, project_id=snap.get("project_id"),
                       cms_type=snap.get("cms_type", "wordpress"), action="rollback",
                       status="success" if result["ok"] else "failed",
                       remote_id=remote_id,
                       error="; ".join(result.get("errors", [])))
    except Exception:
        pass

    # Webhook + audit
    event_type = "page_content.rollback" if result["ok"] else "page_content.rollback_failed"
    _emit(tenant_id, event_type, {"snapshot_id": snapshot_id, "remote_id": remote_id})
    _audit(tenant_id, None, "rollback" if result["ok"] else "rollback_failed",
           "snapshot", snapshot_id, result)

    return {"ok": result["ok"], "status": "rolled_back" if result["ok"] else "failed",
            "snapshot_id": snapshot_id, "remote_id": remote_id,
            "errors": result.get("errors", [])}


def rollback_project(project_id: int, tenant_id: int,
                     snapshot_ids: list[int] = None, dry_run: bool = False) -> dict:
    """批量回滚项目。"""
    results = []
    if snapshot_ids:
        for sid in snapshot_ids:
            results.append(rollback_page_content(sid, tenant_id, dry_run=dry_run))
    return {"ok": True, "results": results, "total": len(results),
            "success": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"])}


def validate_rollback_payload(snapshot: dict) -> dict:
    """验证回滚载荷。"""
    payload = snapshot_to_restore_payload(snapshot)
    issues = []
    if not payload:
        issues.append("Empty restore payload")
    return {"ok": len(issues) == 0, "issues": issues}


def _emit(tenant_id, event_type, payload):
    try:
        from lib.webhooks import create_webhook_event
        create_webhook_event(tenant_id, event_type, payload)
    except Exception:
        pass


def _audit(tenant_id, user_id, action, resource_type, resource_id, details):
    try:
        from lib.audit_log import create_audit_log
        create_audit_log(tenant_id, user_id, action, resource_type, resource_id, details)
    except Exception:
        pass
