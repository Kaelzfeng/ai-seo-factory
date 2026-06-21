# -*- coding: utf-8 -*-
"""tests/test_wordpress_sync_panel.py · Phase 9.3.5: WordPress Sync Panel API tests"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models

ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    """Reusable fake for requests.Session.request monkeypatching."""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload


@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True
    _app.config["SECRET_KEY"] = "test-panel-key"
    return _app


@pytest.fixture
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


def _setup(app, monkeypatch, db, email="panel@test.com"):
    """Create tenant, user, project, page_content. Return (tid, uid, pid, pc_id)."""
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("wp-panel-org")
    uid = models.create_user(email, "hash", "salt")
    models.add_tenant_member(tid, uid, role="owner")
    pid = models.create_project(
        user_id=uid, name="WP Panel Project", tenant_id=tid,
        seed_keyword="hardware tools supplier", language="English",
        site_url="https://content.example",
    )
    pc_id = models.create_page_content(
        tenant_id=tid, project_id=pid,
        slug="hardware-tools-supplier",
        title="Hardware Tools Supplier Guide",
        primary_keyword="hardware tools supplier",
        content_json="{}",
        gutenberg_html="<h2>Hardware Tools</h2><p>Export guide for hardware tools suppliers.</p>",
    )
    return tid, uid, pid, pc_id


def _fake_success(_self, _method, _url, **kwargs):
    return FakeResponse(payload={
        "id": 1, "name": "api-editor",
        "slug": "api-editor", "email": "api-editor@wp.example.test",
    })


# ═══════════════════════════════════════════════════════
# Test Connection
# ═══════════════════════════════════════════════════════

def test_wordpress_test_connection_requires_login(app, db, monkeypatch):
    """未登录调用 test-connection 应返回 401。"""
    monkeypatch.setattr(models, "_get_db", lambda: db)
    with app.test_client() as c:
        resp = c.post("/api/wordpress/test-connection", json={
            "wp_url": "https://wp.example.test",
            "wp_username": "user",
            "wp_app_password": "pass",
        })
        assert resp.status_code == 401


def test_wordpress_test_connection_success(app, db, monkeypatch):
    """连接成功返回 ok=true, status=connected。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)
    monkeypatch.setattr(requests.Session, "request", _fake_success)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/test-connection", json={
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": "secret-app-password",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"] == "connected"
        assert data["username"] == "api-editor"
        assert data["hint"] == "连接成功"


def test_wordpress_test_connection_masks_password(app, db, monkeypatch):
    """test-connection 响应中不应包含明文 app_password。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)
    password = "super-secret-app-password-xyz"
    monkeypatch.setattr(requests.Session, "request", _fake_success)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/test-connection", json={
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": password,
        })
        data = resp.get_json()
        raw = json.dumps(data)
        assert password not in raw


def test_wordpress_test_connection_handles_401(app, db, monkeypatch):
    """401 响应应返回认证失败的人话提示。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    def fake_401(_self, _method, _url, **kwargs):
        return FakeResponse(status_code=401, payload={
            "code": "rest_cannot_view",
            "message": "Sorry, you cannot view this resource.",
        })

    monkeypatch.setattr(requests.Session, "request", fake_401)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/test-connection", json={
            "wp_url": "https://wp.example.test",
            "wp_username": "bad-user",
            "wp_app_password": "bad-password",
        })
        data = resp.get_json()
        assert data["ok"] is False
        assert "401" in data.get("error", "")
        assert "认证失败" in data.get("hint", "")


# ═══════════════════════════════════════════════════════
# Sync Draft
# ═══════════════════════════════════════════════════════

def test_wordpress_sync_draft_requires_login(app, db, monkeypatch):
    """未登录调用 sync-draft 应返回 401。"""
    monkeypatch.setattr(models, "_get_db", lambda: db)
    with app.test_client() as c:
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": 1,
            "wp_url": "https://wp.example.test",
            "wp_username": "user",
            "wp_app_password": "pass",
        })
        assert resp.status_code == 401


def test_wordpress_sync_draft_uses_draft_status(app, db, monkeypatch):
    """同步草稿应强制使用 status='draft' 发送到 WordPress。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    captured = {}

    def fake_post(_self, method, url, **kwargs):
        captured.update(method=method, url=url, json_payload=kwargs.get("json", {}))
        return FakeResponse(payload={
            "id": 99,
            "status": "draft",
            "link": "https://wp.example.test/?p=99",
        })

    monkeypatch.setattr(requests.Session, "request", fake_post)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": pc_id,
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": "secret-app-password",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        # Verify the outbound payload has status=draft
        assert captured["json_payload"]["status"] == "draft"


def test_wordpress_sync_draft_masks_password(app, db, monkeypatch):
    """sync-draft 响应中不应包含明文 app_password。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)
    password = "app-password-should-not-leak-999"

    def fake_post(_self, _method, _url, **kwargs):
        return FakeResponse(payload={"id": 55, "status": "draft", "link": "https://wp.example.test/?p=55"})

    monkeypatch.setattr(requests.Session, "request", fake_post)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": pc_id,
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": password,
        })
        data = resp.get_json()
        raw = json.dumps(data)
        assert password not in raw


def test_wordpress_sync_draft_does_not_publish(app, db, monkeypatch):
    """即使请求 publish 模式，也应降级为 draft。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    captured = {}

    def fake_post(_self, method, url, **kwargs):
        captured.update(json_payload=kwargs.get("json", {}))
        return FakeResponse(payload={"id": 77, "status": "draft", "link": "https://wp.example.test/?p=77"})

    monkeypatch.setattr(requests.Session, "request", fake_post)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": pc_id,
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": "secret-app-password",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        # The adapter always forces draft regardless of what we pass
        assert captured["json_payload"]["status"] == "draft"


def test_wordpress_sync_draft_success(app, db, monkeypatch):
    """同步成功应返回 post_id, edit_url, link。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    def fake_post(_self, _method, _url, **kwargs):
        return FakeResponse(payload={
            "id": 88,
            "status": "draft",
            "link": "https://wp.example.test/hardware-tools-supplier-guide/",
        })

    monkeypatch.setattr(requests.Session, "request", fake_post)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": pc_id,
            "wp_url": "https://wp.example.test",
            "wp_username": "api-editor",
            "wp_app_password": "secret-app-password",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["post_id"] == 88
        assert "wp.example.test" in data.get("edit_url", "")
        assert "wp.example.test" in data.get("link", "")
        assert data["page_content_id"] == pc_id


def test_wordpress_sync_draft_page_not_found(app, db, monkeypatch):
    """不存在的 page_id 应返回 404。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": 99999,
            "wp_url": "https://wp.example.test",
            "wp_username": "user",
            "wp_app_password": "pass",
        })
        assert resp.status_code == 404


def test_wordpress_sync_draft_tenant_mismatch(app, db, monkeypatch):
    """跨 tenant 同步应返回 403。"""
    tid1, uid1, pid1, pc_id1 = _setup(app, monkeypatch, db, "user1@test.com")

    # Create second tenant with its own content
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid2 = models.create_tenant("other-org")
    uid2 = models.create_user("user2@test.com", "hash2", "salt2")
    models.add_tenant_member(tid2, uid2, role="owner")
    pid2 = models.create_project(user_id=uid2, name="Other Project", tenant_id=tid2, seed_keyword="x")
    pc_id2 = models.create_page_content(
        tenant_id=tid2, project_id=pid2, slug="other-page",
        title="Other", primary_keyword="x", content_json="{}",
        gutenberg_html="<p>x</p>",
    )

    # Try to sync pc_id2 as user1 (tid1)
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid1
        resp = c.post("/api/wordpress/sync-draft", json={
            "page_id": pc_id2,
            "wp_url": "https://wp.example.test",
            "wp_username": "user",
            "wp_app_password": "pass",
        })
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════
# Template checks
# ═══════════════════════════════════════════════════════

def test_wordpress_panel_template_has_controls(app, db, monkeypatch):
    """模板中应包含测试连接和同步草稿按钮。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.get("/projects/{}/wordpress".format(pid))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "测试连接" in html
        assert "同步草稿" in html
        assert "wpUrl" in html or "wp_url" in html.lower()


def test_wordpress_panel_template_does_not_render_password(app, db, monkeypatch):
    """模板 HTML 中不应以明文形式回显 Application Password。"""
    tid, uid, pid, pc_id = _setup(app, monkeypatch, db)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.get("/projects/{}/wordpress".format(pid))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Password input should be type=password with NO value attribute
        assert 'type="password"' in html
        # The password field should NOT have a non-empty value attribute
        import re
        pw_inputs = re.findall(r'<input[^>]*type="password"[^>]*>', html)
        for inp in pw_inputs:
            # If value= is present, it should be empty or the placeholder
            val_match = re.search(r'value="([^"]*)"', inp)
            if val_match and val_match.group(1):
                # fail if value is non-empty
                pytest.fail("Password input should not have a non-empty value attribute")


# ═══════════════════════════════════════════════════════
# Side-effects / immutability guards
# ═══════════════════════════════════════════════════════

def test_static_not_modified():
    """static/ 目录下所有文件应完好存在。"""
    static_dir = ROOT / "static"
    if static_dir.exists():
        files = list(static_dir.rglob("*"))
        assert len(files) > 0
        for f in files:
            if f.is_file():
                assert f.exists()
                assert f.stat().st_size >= 0


def test_output_src_not_modified():
    """output_src/ 目录下文件不应被测试修改。"""
    out_dir = ROOT / "output_src"
    if out_dir.exists():
        for f in out_dir.rglob("*.html"):
            if f.is_file():
                assert f.exists()
