# -*- coding: utf-8 -*-
"""tests/test_sites.py · 站点管理测试

覆盖:
1. site 创建后归属正确 tenant
2. 不能读取其他 tenant 的 site
3. validate_site_config 验证
4. project 不存在时报错
5. project 不属于 tenant 时报错
6. 不支持的 cms_type 报错
7. WordPress 配置不完整报错
8. 从 project 字段回退获取默认 site
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models


# ── Fixture ─────────────────────────────────────────


@pytest.fixture()
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    yield conn
    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def _setup_tenant_and_project(conn, monkeypatch):
    """创建 tenant + project, 注入隔离 DB。"""
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    tid = models.create_tenant("test-org")
    uid = models.create_user("test@example.com", "hash", "salt")
    pid = models.create_project(
        user_id=uid, name="test-project",
        tenant_id=tid, seed_keyword="test",
        site_url="https://example.com",
        wp_url="https://example.com/wp-json",
        wp_username="admin",
        wp_app_password="pass123",
    )
    return tid, uid, pid


# ── Test: site 创建后归属正确 tenant ────────────────


def test_create_site_belongs_to_correct_tenant(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)

    from lib.sites import create_site
    site = create_site(
        tenant_id=tid, project_id=pid, name="My WP Site",
        cms_type="wordpress", site_url="https://example.com",
        wp_url="https://example.com/wp-json",
        wp_username="admin", wp_app_password="pass123",
    )
    assert site is not None
    assert site["tenant_id"] == tid
    assert site["project_id"] == pid
    assert site["name"] == "My WP Site"
    assert site["cms_type"] == "wordpress"
    assert site["status"] == "active"


# ── Test: 不能读取其他 tenant 的 site ───────────────


def test_cannot_read_other_tenant_site(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)

    from lib.sites import create_site, get_site
    site = create_site(
        tenant_id=tid, project_id=pid, name="Site A",
        cms_type="wordpress", site_url="https://example.com",
        wp_url="https://example.com/wp-json",
        wp_username="admin", wp_app_password="pass123",
    )

    # 另一个 tenant
    tid2 = models.create_tenant("other-org")

    # 用 tenant_id 过滤读取 — 应返回 None
    result = get_site(site["id"], tenant_id=tid2)
    assert result is None

    # 用自己的 tenant_id 可以读到
    result = get_site(site["id"], tenant_id=tid)
    assert result is not None
    assert result["id"] == site["id"]


# ── Test: list_sites 按 tenant 过滤 ─────────────────


def test_list_sites_by_tenant(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)

    from lib.sites import create_site, list_sites

    create_site(tenant_id=tid, project_id=pid, name="Site 1",
                cms_type="wordpress", site_url="https://a.com",
                wp_url="https://a.com/wp-json", wp_username="u", wp_app_password="p")
    create_site(tenant_id=tid, project_id=pid, name="Site 2",
                cms_type="wordpress", site_url="https://b.com",
                wp_url="https://b.com/wp-json", wp_username="u", wp_app_password="p")

    sites = list_sites(tenant_id=tid)
    assert len(sites) == 2

    tid2 = models.create_tenant("empty-org")
    sites2 = list_sites(tenant_id=tid2)
    assert len(sites2) == 0


# ── Test: validate_site_config ──────────────────────


def test_validate_site_config_wordpress_ok():
    from lib.sites import validate_site_config
    # 不抛异常即通过
    validate_site_config(
        cms_type="wordpress",
        site_url="https://example.com",
        wp_url="https://example.com/wp-json",
        wp_username="admin",
        wp_app_password="pass123",
    )


def test_validate_site_config_missing_cms_type():
    from lib.sites import validate_site_config, SiteError
    with pytest.raises(SiteError, match="cms_type 不能为空"):
        validate_site_config(cms_type="")


def test_validate_site_config_unsupported_cms_type():
    from lib.sites import validate_site_config, SiteError
    with pytest.raises(SiteError, match="不支持的 cms_type"):
        validate_site_config(cms_type="drupal")


def test_validate_site_config_missing_wp_url():
    from lib.sites import validate_site_config, SiteError
    with pytest.raises(SiteError, match="wp_url"):
        validate_site_config(
            cms_type="wordpress",
            site_url="https://example.com",
            wp_url="",
            wp_username="admin",
            wp_app_password="pass",
        )


def test_validate_site_config_missing_wp_username():
    from lib.sites import validate_site_config, SiteError
    with pytest.raises(SiteError, match="wp_username"):
        validate_site_config(
            cms_type="wordpress",
            site_url="https://example.com",
            wp_url="https://example.com/wp-json",
            wp_username="",
            wp_app_password="pass",
        )


def test_validate_site_config_missing_site_url():
    from lib.sites import validate_site_config, SiteError
    with pytest.raises(SiteError, match="site_url"):
        validate_site_config(
            cms_type="wordpress",
            site_url="",
            wp_url="https://example.com/wp-json",
            wp_username="admin",
            wp_app_password="pass",
        )


# ── Test: project 不存在时报错 ─────────────────────


def test_create_site_project_not_found(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)
    from lib.sites import create_site, SiteError

    with pytest.raises(SiteError, match="项目 99999 不存在"):
        create_site(
            tenant_id=tid, project_id=99999, name="Bad",
            cms_type="wordpress", site_url="https://x.com",
            wp_url="https://x.com/wp-json", wp_username="u", wp_app_password="p",
        )


# ── Test: project 不属于 tenant 时报错 ──────────────


def test_create_site_tenant_mismatch(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)
    # 创建不属于 tid 的 project
    tid2 = models.create_tenant("other")
    uid2 = models.create_user("other@test.com", "h", "s")
    pid2 = models.create_project(
        user_id=uid2, name="other-proj", tenant_id=tid2, seed_keyword="x",
    )
    monkeypatch.setattr(models, "_get_db", lambda: db)

    from lib.sites import create_site, SiteError
    with pytest.raises(SiteError, match="不属于 tenant"):
        create_site(
            tenant_id=tid, project_id=pid2, name="Bad",
            cms_type="wordpress", site_url="https://x.com",
            wp_url="https://x.com/wp-json", wp_username="u", wp_app_password="p",
        )


# ── Test: get_project_default_site 回退到 project 字段 ──


def test_get_project_default_site_fallback(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)

    from lib.sites import get_project_default_site
    site = get_project_default_site(pid)
    assert site is not None
    assert site["cms_type"] == "wordpress"
    assert site["wp_url"] == "https://example.com/wp-json"
    assert site["wp_username"] == "admin"
    assert site["wp_app_password"] == "pass123"


def test_get_project_default_site_prefers_db_site(db, monkeypatch):
    tid, uid, pid = _setup_tenant_and_project(db, monkeypatch)

    from lib.sites import create_site, get_project_default_site
    site1 = create_site(
        tenant_id=tid, project_id=pid, name="DB Site",
        cms_type="wordpress", site_url="https://dbsite.com",
        wp_url="https://dbsite.com/wp-json", wp_username="u", wp_app_password="p",
    )

    site = get_project_default_site(pid)
    assert site is not None
    assert site["id"] == site1["id"]
    assert site["name"] == "DB Site"
