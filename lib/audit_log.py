# -*- coding: utf-8 -*-
"""lib/audit_log.py · Phase 6: 审计日志"""

import json


def create_audit_log(tenant_id: int, user_id: int = None,
                     action: str = "", resource_type: str = "",
                     resource_id: int = None, details: dict = None) -> int:
    from models import create_audit_log_record
    return create_audit_log_record(
        tenant_id=tenant_id, user_id=user_id, action=action,
        resource_type=resource_type, resource_id=resource_id,
        details_json=json.dumps(details or {}, ensure_ascii=False),
    )


def list_audit_logs(tenant_id: int, resource_type: str = None,
                    resource_id: int = None, limit: int = 100) -> list[dict]:
    from models import list_audit_log_records
    return list_audit_log_records(
        tenant_id=tenant_id, resource_type=resource_type,
        resource_id=resource_id, limit=limit,
    )


def audit_publish_action(tenant_id: int, user_id: int = None,
                         page_content_id: int = None, details: dict = None):
    return create_audit_log(tenant_id, user_id, "publish", "page_content", page_content_id, details)


def audit_rollback_action(tenant_id: int, user_id: int = None,
                          snapshot_id: int = None, details: dict = None):
    return create_audit_log(tenant_id, user_id, "rollback", "snapshot", snapshot_id, details)
