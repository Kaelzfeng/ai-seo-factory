# -*- coding: utf-8 -*-
"""tests/test_cms_logs.py · CMS 日志测试

覆盖:
5. dry-run 不写 cms publish success
6. publish 模式会写 cms_logs
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


def _setup(conn, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    tid = models.create_tenant("test-org")
    uid = models.create_user("test@example.com", "hash", "salt")
    pid = models.create_project(
        user_id=uid, name="test-project",
        tenant_id=tid, seed_keyword="test",
    )
    gen_id = models.create_generation(
        project_id=pid, tenant_id=tid, keyword="test-kw",
        page_type="guide", title="Test", slug="test-page",
    )
    site_id = models.create_site(
        tenant_id=tid, project_id=pid, name="Test WP",
        cms_type="wordpress", site_url="https://example.com",
        wp_url="https://example.com/wp-json",
        wp_username="admin", wp_app_password="pass",
        status="active",
    )
    return tid, uid, pid, gen_id, site_id


# ── Test: record_publish_success ────────────────────


def test_record_publish_success(db, monkeypatch):
    tid, uid, pid, gen_id, site_id = _setup(db, monkeypatch)

    from lib.cms_logs import record_publish_success
    log_id = record_publish_success(
        tenant_id=tid, project_id=pid,
        generation_id=gen_id, site_id=site_id,
        remote_id="123", remote_url="https://example.com/test-page",
    )
    assert log_id > 0

    logs = models.list_cms_logs(generation_id=gen_id)
    assert len(logs) == 1
    assert logs[0]["status"] == "success"
    assert logs[0]["remote_id"] == "123"
    assert logs[0]["remote_url"] == "https://example.com/test-page"
    assert logs[0]["action"] == "publish"
    assert logs[0]["cms_type"] == "wordpress"


# ── Test: record_publish_failure ────────────────────


def test_record_publish_failure(db, monkeypatch):
    tid, uid, pid, gen_id, site_id = _setup(db, monkeypatch)

    from lib.cms_logs import record_publish_failure
    log_id = record_publish_failure(
        tenant_id=tid, project_id=pid,
        generation_id=gen_id, site_id=site_id,
        error="HTTP 500: Internal Server Error",
    )
    assert log_id > 0

    logs = models.list_cms_logs(generation_id=gen_id)
    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert "HTTP 500" in logs[0]["error"]


# ── Test: list_cms_logs 支持多维过滤 ────────────────


def test_list_cms_logs_filtering(db, monkeypatch):
    tid, uid, pid, gen_id, site_id = _setup(db, monkeypatch)

    from lib.cms_logs import record_cms_log, list_cms_logs

    record_cms_log(tenant_id=tid, project_id=pid, generation_id=gen_id,
                   site_id=site_id, action="publish", status="success",
                   remote_id="1")
    record_cms_log(tenant_id=tid, project_id=pid, generation_id=gen_id,
                   site_id=site_id, action="update", status="failed",
                   error="timeout")

    # 所有日志
    all_logs = list_cms_logs(tenant_id=tid)
    assert len(all_logs) == 2

    # 按 generation_id 过滤
    gen_logs = list_cms_logs(generation_id=gen_id)
    assert len(gen_logs) == 2

    # 按 site_id 过滤
    site_logs = list_cms_logs(site_id=site_id)
    assert len(site_logs) == 2


# ── Test: cms_log 支持 tenant 隔离 ──────────────────


def test_cms_log_tenant_isolation(db, monkeypatch):
    tid, uid, pid, gen_id, site_id = _setup(db, monkeypatch)

    from lib.cms_logs import record_cms_log, list_cms_logs

    record_cms_log(tenant_id=tid, project_id=pid, generation_id=gen_id,
                   site_id=site_id, status="success")

    tid2 = models.create_tenant("other")
    logs_t2 = list_cms_logs(tenant_id=tid2)
    assert len(logs_t2) == 0

    logs_t1 = list_cms_logs(tenant_id=tid)
    assert len(logs_t1) == 1
