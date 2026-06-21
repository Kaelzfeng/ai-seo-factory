# -*- coding: utf-8 -*-
"""lib/publish_sync.py · Phase 6: 发布同步

把 page_contents 同步到 CMS。
"""

import json
import os

from lib.cms_field_mapper import map_page_content_to_cms_fields
from lib.cms_adapter import get_cms_adapter
from lib.publish_snapshot import create_publish_snapshot


def _page_to_dict(pc) -> dict:
    if hasattr(pc, "to_dict"):
        return pc.to_dict()
    return pc


def _provider_name(cms_type: str) -> str:
    return "wordpress_real" if cms_type in {"wordpress", "wordpress_real"} else "mock"


def _wordpress_config(project_id: int = None) -> tuple[dict, int | None]:
    """Resolve credentials without ever adding them to sync results or logs."""
    site = None
    if project_id is not None:
        try:
            from lib.sites import get_project_default_site
            site = get_project_default_site(project_id)
        except Exception:
            site = None
    site = site or {}

    timeout = os.getenv("WP_TIMEOUT", "20")
    config = {
        "base_url": (
            site.get("wp_url")
            or site.get("site_url")
            or os.getenv("WP_BASE_URL")
            or os.getenv("WP_SITE")
            or ""
        ),
        "username": (
            site.get("wp_username")
            or os.getenv("WP_USERNAME")
            or os.getenv("WP_USER")
            or ""
        ),
        "app_password": (
            site.get("wp_app_password")
            or os.getenv("WP_APP_PASSWORD")
            or ""
        ),
        "timeout": timeout,
    }
    return config, site.get("id")


def _planned_payload(mapping: dict) -> dict:
    payload = {
        "title": mapping.get("title", ""),
        "content": mapping.get("content", ""),
        "status": "draft",
    }
    for name in ("slug", "excerpt", "categories", "tags"):
        value = mapping.get(name)
        if value:
            payload[name] = value
    return payload


def sync_page_content(page_content_id: int, tenant_id: int,
                      project_id: int = None, cms_type: str = "wordpress",
                      mode: str = "draft", dry_run: bool = False) -> dict:
    """同步单页 PageContent 到 CMS。"""
    from models import get_page_content

    cms_type = str(cms_type or "wordpress").lower()
    provider = _provider_name(cms_type)
    pc = get_page_content(page_content_id)
    if pc is None:
        return {
            "ok": False, "provider": provider, "status": "failed",
            "post_id": None, "edit_url": "", "link": "", "warning": "",
            "error": "PageContent not found", "page_content_id": page_content_id,
            "errors": ["PageContent not found"],
        }
    if tenant_id is not None and pc.get("tenant_id") != tenant_id:
        return {
            "ok": False, "provider": provider, "status": "failed",
            "post_id": None, "edit_url": "", "link": "", "warning": "",
            "error": "Tenant mismatch", "page_content_id": page_content_id,
            "errors": ["Tenant mismatch"],
        }

    project_id = project_id or pc.get("project_id")
    requested_mode = str(mode or "draft").lower()
    is_dry_run = dry_run or requested_mode in {"dry-run", "dry_run"}
    warning = ""
    if requested_mode not in {"draft", "sync", "dry-run", "dry_run"}:
        warning = f"Requested status '{requested_mode}' was restricted to draft."

    # Field mapping
    mapping = map_page_content_to_cms_fields(pc)
    before_json = json.dumps(pc, ensure_ascii=False)

    if is_dry_run:
        return {
            "ok": True, "provider": provider, "status": "dry_run",
            "post_id": None, "edit_url": "", "link": "",
            "warning": warning, "error": "", "page_content_id": page_content_id,
            "mapped_fields": mapping, "snapshot_id": None, "remote_id": "",
            "remote_url": "", "errors": [],
            "planned_payload": _planned_payload(mapping),
        }

    # Create snapshot (before)
    snap_id = create_publish_snapshot(
        page_content_id=page_content_id, tenant_id=tenant_id,
        project_id=project_id, cms_type=cms_type,
        before_json=before_json,
        remote_id="", remote_url="",
    )

    # Get adapter. Credentials stay inside the adapter and never enter results.
    adapter_config = None
    site_id = None
    if provider == "wordpress_real":
        adapter_config, site_id = _wordpress_config(project_id)
    adapter = get_cms_adapter(cms_type, adapter_config)

    # Phase 9.3.4 is draft-only, including callers that request publish.
    result = adapter.publish_draft(pc, mapping)
    result_warning = result.get("warning", "")
    warnings = [item for item in (warning, result_warning) if item]
    warning = " ".join(dict.fromkeys(warnings))
    error = result.get("error") or "; ".join(result.get("errors", []))
    post_id = result.get("post_id")
    if post_id is None:
        post_id = result.get("remote_id") or None
    link = result.get("link") or result.get("remote_url", "")

    # Write cms_log
    try:
        from lib.cms_logs import record_cms_log
        record_cms_log(tenant_id=tenant_id, project_id=project_id,
                       generation_id=pc.get("generation_id"),
                       site_id=site_id, cms_type=cms_type, action="draft",
                       status="success" if result["ok"] else "failed",
                       remote_id=str(post_id) if post_id is not None else "",
                       remote_url=link,
                       error=error,
                       meta={"page_content_id": page_content_id})
    except Exception:
        pass

    # Write webhook event
    event_type = "page_content.synced" if result["ok"] else "page_content.sync_failed"
    _emit_event(tenant_id, event_type, {
        "page_content_id": page_content_id,
        "remote_id": str(post_id) if post_id is not None else "",
        "status": result.get("status", ""),
    })

    # Write audit log
    normalized = {
        "ok": result["ok"],
        "provider": result.get("provider", provider),
        "status": result.get("status", "draft" if result["ok"] else "failed"),
        "post_id": post_id,
        "edit_url": result.get("edit_url", ""),
        "link": link,
        "warning": warning,
        "error": error,
        "page_content_id": page_content_id,
        "remote_id": str(post_id) if post_id is not None else "",
        "remote_url": link,
        "snapshot_id": snap_id,
        "errors": [error] if error else [],
    }

    _audit(tenant_id, None, "publish_sync" if result["ok"] else "publish_sync_failed",
           "page_content", page_content_id, normalized)

    return normalized


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
