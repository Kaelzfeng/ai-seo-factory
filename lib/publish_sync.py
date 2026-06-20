# -*- coding: utf-8 -*-
"""lib/publish_sync.py · Phase 6: 发布同步

把 page_contents 同步到 CMS。
"""

import json

from lib.cms_field_mapper import map_page_content_to_cms_fields
from lib.cms_adapter import get_cms_adapter
from lib.publish_snapshot import create_publish_snapshot


def _page_to_dict(pc) -> dict:
    if hasattr(pc, "to_dict"):
        return pc.to_dict()
    return pc


def sync_page_content(page_content_id: int, tenant_id: int,
                      project_id: int = None, cms_type: str = "wordpress",
                      mode: str = "draft", dry_run: bool = False) -> dict:
    """同步单页 PageContent 到 CMS。"""
    from models import get_page_content

    pc = get_page_content(page_content_id)
    if pc is None:
        return {"ok": False, "status": "failed", "page_content_id": page_content_id,
                "errors": ["PageContent not found"]}
    if tenant_id is not None and pc.get("tenant_id") != tenant_id:
        return {"ok": False, "status": "failed", "page_content_id": page_content_id,
                "errors": ["Tenant mismatch"]}

    # Field mapping
    mapping = map_page_content_to_cms_fields(pc)
    before_json = json.dumps(pc, ensure_ascii=False)

    if dry_run:
        return {
            "ok": True, "status": "dry_run", "page_content_id": page_content_id,
            "mapped_fields": mapping, "snapshot_id": None, "remote_id": "",
            "remote_url": "", "errors": [],
        }

    # Create snapshot (before)
    snap_id = create_publish_snapshot(
        page_content_id=page_content_id, tenant_id=tenant_id,
        project_id=project_id, cms_type=cms_type,
        before_json=before_json,
        remote_id="", remote_url="",
    )

    # Get adapter
    adapter = get_cms_adapter(cms_type)

    # Publish
    if mode == "draft":
        result = adapter.publish_draft(pc, mapping)
    else:
        result = adapter.publish_now(pc, mapping)

    # Write cms_log
    try:
        from lib.cms_logs import record_cms_log
        record_cms_log(tenant_id=tenant_id, project_id=project_id,
                       generation_id=pc.get("generation_id"),
                       site_id=None, cms_type=cms_type, action=mode,
                       status="success" if result["ok"] else "failed",
                       remote_id=result.get("remote_id", ""),
                       remote_url=result.get("remote_url", ""),
                       error="; ".join(result.get("errors", [])),
                       meta={"page_content_id": page_content_id})
    except Exception:
        pass

    # Write webhook event
    event_type = "page_content.synced" if result["ok"] else "page_content.sync_failed"
    _emit_event(tenant_id, event_type, {
        "page_content_id": page_content_id,
        "remote_id": result.get("remote_id", ""),
        "status": result.get("status", ""),
    })

    # Write audit log
    _audit(tenant_id, None, "publish_sync" if result["ok"] else "publish_sync_failed",
           "page_content", page_content_id, result)

    return {
        "ok": result["ok"],
        "status": "synced" if result["ok"] else "failed",
        "page_content_id": page_content_id,
        "remote_id": result.get("remote_id", ""),
        "remote_url": result.get("remote_url", ""),
        "snapshot_id": snap_id,
        "errors": result.get("errors", []),
    }


def sync_project_pages(project_id: int, tenant_id: int,
                       cms_type: str = "wordpress", mode: str = "draft",
                       dry_run: bool = False, limit: int = None) -> dict:
    """批量同步项目的所有 page_contents。"""
    from models import list_page_contents

    pages = list_page_contents(tenant_id=tenant_id, project_id=project_id)
    if limit:
        pages = pages[:limit]

    results = []
    success = 0
    failed = 0

    for pc in pages:
        res = sync_page_content(pc["id"], tenant_id=tenant_id,
                               project_id=project_id, cms_type=cms_type,
                               mode=mode, dry_run=dry_run)
        results.append(res)
        if res["ok"]:
            success += 1
        else:
            failed += 1

    _emit_event(tenant_id, "project.sync_completed" if failed == 0 else "project.sync_failed", {
        "project_id": project_id, "total": len(pages), "success": success, "failed": failed,
    })

    return {"ok": failed == 0, "total": len(pages), "success": success,
            "failed": failed, "results": results}


def retry_failed_syncs(project_id: int = None, tenant_id: int = None) -> dict:
    """重试失败的同步 (stub)。"""
    return {"ok": True, "message": "retry_failed_syncs not yet implemented", "retried": 0}


def get_sync_status(page_content_id: int, tenant_id: int) -> dict:
    """获取同步状态。"""
    from models import list_publish_snapshot_records
    snaps = list_publish_snapshot_records(page_content_id=page_content_id, tenant_id=tenant_id)
    latest = snaps[0] if snaps else None
    return {"page_content_id": page_content_id, "last_snapshot": latest,
            "snapshot_count": len(snaps)}


def _emit_event(tenant_id, event_type, payload):
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
