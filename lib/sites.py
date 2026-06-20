# -*- coding: utf-8 -*-
"""lib/sites.py · 站点管理

提供站点 CRUD 与验证,不接新前端。

要求:
- site 必须属于 tenant
- project_id 必须匹配 tenant
- cms_type 先支持 wordpress
"""

from models import (
    create_site as _create_site,
    get_site as _get_site,
    list_sites as _list_sites,
    update_site as _update_site,
    get_project,
)


class SiteError(Exception):
    """站点相关错误。"""
    def __init__(self, message: str, code: str = "site_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _validate_wordpress_config(site_url: str, wp_url: str,
                                wp_username: str, wp_app_password: str):
    """验证 WordPress 站点配置完整性。"""
    missing = []
    if not wp_url or not wp_url.strip():
        missing.append("wp_url")
    if not wp_username or not wp_username.strip():
        missing.append("wp_username")
    if not wp_app_password or not wp_app_password.strip():
        missing.append("wp_app_password")
    if missing:
        raise SiteError(
            f"WordPress 配置不完整,缺少: {', '.join(missing)}",
            code="incomplete_wp_config",
        )
    if not site_url or not site_url.strip():
        raise SiteError(
            "site_url 不能为空",
            code="missing_site_url",
        )


def validate_site_config(cms_type: str, site_url: str = "",
                         wp_url: str = "", wp_username: str = "",
                         wp_app_password: str = ""):
    """验证站点配置。

    Args:
        cms_type: "wordpress" (目前唯一支持)
        site_url: 公开网站 URL
        wp_url: WordPress REST API URL
        wp_username: WordPress 用户名
        wp_app_password: WordPress Application Password

    Raises:
        SiteError: 配置不完整或无效
    """
    cms_type = (cms_type or "").strip().lower()
    if not cms_type:
        raise SiteError("cms_type 不能为空", code="missing_cms_type")
    if cms_type == "wordpress":
        _validate_wordpress_config(
            site_url=site_url,
            wp_url=wp_url,
            wp_username=wp_username,
            wp_app_password=wp_app_password,
        )
    else:
        raise SiteError(
            f"不支持的 cms_type: {cms_type} (目前只支持 wordpress)",
            code="unsupported_cms_type",
        )


def create_site(tenant_id: int, project_id: int, name: str,
                cms_type: str = "wordpress", site_url: str = "",
                wp_url: str = "", wp_username: str = "",
                wp_app_password: str = "") -> dict:
    """创建站点。

    验证:
    - project 存在且属于该 tenant
    - cms_type 配置完整

    Returns:
        site dict
    """
    # 验证 project 属于 tenant
    proj = get_project(project_id)
    if proj is None:
        raise SiteError(f"项目 {project_id} 不存在", code="project_not_found")
    if proj.get("tenant_id") != tenant_id:
        raise SiteError(
            f"项目 {project_id} 不属于 tenant {tenant_id}",
            code="tenant_mismatch",
        )

    # 验证站点配置
    validate_site_config(cms_type, site_url, wp_url, wp_username, wp_app_password)

    site_id = _create_site(
        tenant_id=tenant_id,
        project_id=project_id,
        name=name,
        cms_type=cms_type,
        site_url=site_url,
        wp_url=wp_url,
        wp_username=wp_username,
        wp_app_password=wp_app_password,
        status="active",
    )
    return _get_site(site_id)


def get_site(site_id: int, tenant_id: int = None) -> dict | None:
    """获取站点详情。

    如果提供 tenant_id,则校验归属；不匹配返回 None。
    """
    site = _get_site(site_id)
    if site is None:
        return None
    if tenant_id is not None and site.get("tenant_id") != tenant_id:
        return None
    return site


def list_sites(tenant_id: int = None, project_id: int = None) -> list[dict]:
    """列出站点。按 tenant 或 project 过滤。"""
    return _list_sites(tenant_id=tenant_id, project_id=project_id)


def get_project_default_site(project_id: int) -> dict | None:
    """获取项目的默认(第一个 active)站点。

    如果项目没有独立 site 记录,尝试从 project 的 wp_* 字段构造回退 site。
    """
    sites = _list_sites(project_id=project_id)
    active_sites = [s for s in sites if s.get("status") == "active"]
    if active_sites:
        return active_sites[0]

    # 回退:从 project 的 wp_* 字段构造
    proj = get_project(project_id)
    if proj and proj.get("wp_url"):
        return {
            "id": None,
            "tenant_id": proj.get("tenant_id"),
            "project_id": project_id,
            "name": proj.get("name", ""),
            "cms_type": "wordpress",
            "site_url": proj.get("site_url", ""),
            "wp_url": proj.get("wp_url", ""),
            "wp_username": proj.get("wp_username", ""),
            "wp_app_password": proj.get("wp_app_password", ""),
            "status": "active",
            "created_at": proj.get("created_at", ""),
        }
    return None
