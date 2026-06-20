# -*- coding: utf-8 -*-
"""lib/cms_logs.py · CMS 操作日志

publish 模式调用 wp_publish 后必须记录。
成功记录 remote_id / remote_url。
失败记录 error。
"""

import json

from models import (
    create_cms_log as _create_log,
    list_cms_logs as _list_logs,
)


def record_cms_log(tenant_id: int = None, project_id: int = None,
                   generation_id: int = None, site_id: int = None,
                   cms_type: str = "wordpress", action: str = "publish",
                   status: str = "pending", remote_id: str = "",
                   remote_url: str = "", error: str = "",
                   meta: dict = None) -> int:
    """记录一条 CMS 操作日志。

    Args:
        tenant_id: 租户 ID
        project_id: 项目 ID
        generation_id: 关联的 generation ID(单页)
        site_id: 站点 ID
        cms_type: "wordpress"
        action: "publish" | "update" | "delete"
        status: "pending" | "success" | "failed"
        remote_id: CMS 端返回的 ID
        remote_url: CMS 端返回的 URL
        error: 失败时的错误信息
        meta: 附加数据

    Returns:
        cms_log id
    """
    try:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        meta_json = "{}"
    return _create_log(
        tenant_id=tenant_id,
        project_id=project_id,
        generation_id=generation_id,
        site_id=site_id,
        cms_type=cms_type,
        action=action,
        status=status,
        remote_id=str(remote_id),
        remote_url=str(remote_url),
        error=str(error),
        meta_json=meta_json,
    )


def list_cms_logs(tenant_id: int = None, project_id: int = None,
                  generation_id: int = None, site_id: int = None,
                  limit: int = 100) -> list[dict]:
    """列出 CMS 日志,支持多维度过滤。"""
    return _list_logs(
        tenant_id=tenant_id,
        project_id=project_id,
        generation_id=generation_id,
        site_id=site_id,
        limit=limit,
    )


def record_publish_success(tenant_id: int, project_id: int,
                           generation_id: int, site_id: int = None,
                           remote_id: str = "", remote_url: str = "",
                           meta: dict = None) -> int:
    """便捷函数:记录一次成功的发布。"""
    return record_cms_log(
        tenant_id=tenant_id,
        project_id=project_id,
        generation_id=generation_id,
        site_id=site_id,
        cms_type="wordpress",
        action="publish",
        status="success",
        remote_id=remote_id,
        remote_url=remote_url,
        meta=meta,
    )


def record_publish_failure(tenant_id: int, project_id: int,
                           generation_id: int, site_id: int = None,
                           error: str = "", meta: dict = None) -> int:
    """便捷函数:记录一次失败的发布。"""
    return record_cms_log(
        tenant_id=tenant_id,
        project_id=project_id,
        generation_id=generation_id,
        site_id=site_id,
        cms_type="wordpress",
        action="publish",
        status="failed",
        error=error,
        meta=meta,
    )
