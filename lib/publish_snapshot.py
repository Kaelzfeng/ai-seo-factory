# -*- coding: utf-8 -*-
"""lib/publish_snapshot.py · Phase 6: 发布快照

每次发布/更新前创建快照, 用于回滚。
"""

import json
import time


def create_publish_snapshot(page_content_id: int, tenant_id: int,
                            project_id: int = None, cms_type: str = "wordpress",
                            remote_id: str = "", remote_url: str = "",
                            before_json: str = "{}", after_json: str = "{}",
                            remote_json: str = "{}") -> int:
    from models import create_publish_snapshot_record
    return create_publish_snapshot_record(
        tenant_id=tenant_id, project_id=project_id,
        page_content_id=page_content_id, cms_type=cms_type,
        remote_id=remote_id, remote_url=remote_url,
        before_json=before_json, after_json=after_json,
        remote_json=remote_json,
    )


def get_publish_snapshot(snapshot_id: int, tenant_id: int = None) -> dict | None:
    from models import get_publish_snapshot_record
    snap = get_publish_snapshot_record(snapshot_id)
    if snap is None:
        return None
    if tenant_id is not None and snap.get("tenant_id") != tenant_id:
        return None
    return snap


def list_publish_snapshots(project_id: int = None, page_content_id: int = None,
                           tenant_id: int = None) -> list[dict]:
    from models import list_publish_snapshot_records
    return list_publish_snapshot_records(
        tenant_id=tenant_id, project_id=project_id,
        page_content_id=page_content_id,
    )


def snapshot_to_restore_payload(snapshot: dict) -> dict:
    """从快照提取回滚内容。"""
    before = snapshot.get("before_json", "{}")
    try:
        return json.loads(before)
    except (json.JSONDecodeError, TypeError):
        return {}
