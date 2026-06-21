# -*- coding: utf-8 -*-
"""Phase 9.3.4: real WordPress REST adapter and draft sync MVP."""

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

import pytest
import requests

import models


ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, status_code=201, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(db_path)
    yield conn
    conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def _setup_page(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tenant_id = models.create_tenant("wp-real-org")
    user_id = models.create_user("wp-real@test.local", "h", "s")
    project_id = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="WP Draft Sync",
        seed_keyword="hardware tools supplier",
        site_url="https://content.example",
    )
    page_id = models.create_page_content(
        tenant_id=tenant_id,
        project_id=project_id,
        slug="hardware-tools-supplier",
        title="Hardware Tools Supplier",
        primary_keyword="hardware tools supplier",
        content_json="{}",
        gutenberg_html="<h2>Hardware Tools</h2><p>Supplier export guide.</p>",
    )
    return tenant_id, project_id, page_id


def _mock_wordpress_env(monkeypatch, password="app-password-secret"):
    monkeypatch.setenv("WP_BASE_URL", "https://wp.example.test/")
    monkeypatch.setenv("WP_USERNAME", "api-editor")
    monkeypatch.setenv("WP_APP_PASSWORD", password)
    monkeypatch.setenv("WP_TIMEOUT", "20")


def test_wordpress_adapter_builds_correct_endpoint(monkeypatch):
    from lib.cms_wordpress import WordPressAdapter

    captured = {}

    def fake_request(_self, method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return FakeResponse(payload={"id": 42, "status": "draft", "link": "https://wp.example.test/?p=42"})

    monkeypatch.setattr(requests.Session, "request", fake_request)
    adapter = WordPressAdapter(
        "https://wp.example.test/", "api-editor", "app-password-secret"
    )
    adapter.create_post("Title", "<p>Body</p>")

    assert adapter.base_url == "https://wp.example.test"
    assert adapter.posts_endpoint == "https://wp.example.test/wp-json/wp/v2/posts"
    assert captured["method"] == "POST"
    assert captured["url"] == adapter.posts_endpoint


def test_wordpress_adapter_uses_draft_by_default(monkeypatch):
    from lib.cms_wordpress import WordPressAdapter

    captured = {}

    def fake_request(_self, _method, _url, **kwargs):
        captured.update(kwargs)
        return FakeResponse(payload={"id": 7, "status": "draft", "link": "https://wp.example.test/?p=7"})

    monkeypatch.setattr(requests.Session, "request", fake_request)
    result = WordPressAdapter(
        "https://wp.example.test", "api-editor", "secret"
    ).create_post("Title", "<p>Body</p>", status="publish")

    assert captured["json"]["status"] == "draft"
    assert result["status"] == "draft"
    assert "draft" in result["warning"].lower()


def test_wordpress_adapter_masks_password_in_error(monkeypatch, caplog):
    from lib.cms_wordpress import WordPressAdapter

    password = "mask-this-application-password"

    def fail_request(_self, _method, _url, **_kwargs):
        raise requests.ConnectionError(f"authentication failed for {password}")

    monkeypatch.setattr(requests.Session, "request", fail_request)
    caplog.set_level(logging.WARNING)
    result = WordPressAdapter(
        "https://wp.example.test", "api-editor", password
    ).create_post("Title", "<p>Body</p>")

    assert result["ok"] is False
    assert password not in json.dumps(result)
    assert password not in caplog.text
    assert "***" in result["error"]


def test_wordpress_adapter_dry_run_does_not_call_network(monkeypatch):
    from lib.cms_wordpress import WordPressAdapter

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("network must not be called during dry-run")

    monkeypatch.setattr(requests.Session, "request", unexpected_network)
    result = WordPressAdapter(
        "https://wp.example.test", "api-editor", "secret"
    ).create_post("Title", "<p>Body</p>", slug="title", dry_run=True)

    assert result["ok"] is True
    assert result["provider"] == "wordpress_real"
    assert result["status"] == "dry_run"
    assert result["planned_payload"]["status"] == "draft"


def test_sync_dry_run_mode_does_not_call_network(db, monkeypatch):
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    from lib.publish_sync import sync_page_content

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("network must not be called during dry-run")

    monkeypatch.setattr(requests.Session, "request", unexpected_network)
    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="wordpress_real",
        mode="dry-run",
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_payload"]["status"] == "draft"


def test_wordpress_adapter_create_draft_success_with_mocked_requests(monkeypatch):
    from lib.cms_wordpress import WordPressAdapter

    def fake_request(_self, method, url, **kwargs):
        assert method == "POST"
        assert url.endswith("/wp-json/wp/v2/posts")
        assert kwargs["json"]["title"] == "Hardware Tools Supplier"
        assert kwargs["json"]["status"] == "draft"
        assert kwargs["timeout"] == 12
        return FakeResponse(payload={
            "id": 99,
            "status": "draft",
            "link": "https://wp.example.test/?p=99",
        })

    monkeypatch.setattr(requests.Session, "request", fake_request)
    result = WordPressAdapter(
        "https://wp.example.test", "api-editor", "secret", timeout=12
    ).create_draft_post(
        "Hardware Tools Supplier",
        "<p>Draft content</p>",
        slug="hardware-tools-supplier",
        excerpt="Supplier guide",
        categories=[2],
        tags=[5, 8],
    )

    assert result == {
        "ok": True,
        "provider": "wordpress_real",
        "status": "draft",
        "post_id": 99,
        "edit_url": "https://wp.example.test/wp-admin/post.php?post=99&action=edit",
        "link": "https://wp.example.test/?p=99",
        "warning": "",
        "error": "",
    }


def test_wordpress_adapter_handles_timeout(monkeypatch):
    from lib.cms_wordpress import WordPressAdapter

    def timeout(_self, _method, _url, **_kwargs):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr(requests.Session, "request", timeout)
    result = WordPressAdapter(
        "https://wp.example.test", "api-editor", "secret"
    ).create_post("Title", "<p>Body</p>")

    assert result["ok"] is False
    assert result["provider"] == "wordpress_real"
    assert result["status"] == "failed"
    assert result["post_id"] is None
    assert "timed out" in result["error"].lower()


def test_sync_keeps_mock_provider_working(db, monkeypatch):
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    from lib.publish_sync import sync_page_content

    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="mock",
        mode="sync",
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["provider"] == "mock"
    assert result["status"] == "draft"
    assert result["post_id"]


def test_sync_wordpress_real_creates_draft_from_env(db, monkeypatch):
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    _mock_wordpress_env(monkeypatch)
    from lib.cms_wordpress import WordPressAdapter
    from lib.publish_sync import sync_page_content

    captured = {}

    def fake_create(self, title, content, **kwargs):
        captured.update(title=title, content=content, kwargs=kwargs)
        return {
            "ok": True,
            "provider": "wordpress_real",
            "status": "draft",
            "post_id": 123,
            "edit_url": "https://wp.example.test/wp-admin/post.php?post=123&action=edit",
            "link": "https://wp.example.test/?p=123",
            "warning": "",
            "error": "",
        }

    monkeypatch.setattr(WordPressAdapter, "create_post", fake_create)
    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="wordpress_real",
        mode="sync",
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["provider"] == "wordpress_real"
    assert result["status"] == "draft"
    assert result["post_id"] == 123
    assert captured["kwargs"]["status"] == "draft"


def test_sync_publish_request_is_downgraded_to_draft(db, monkeypatch):
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    _mock_wordpress_env(monkeypatch)
    from lib.cms_wordpress import WordPressAdapter
    from lib.publish_sync import sync_page_content

    captured = {}

    def fake_create(self, title, content, **kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "provider": "wordpress_real",
            "status": "draft",
            "post_id": 124,
            "edit_url": "https://wp.example.test/wp-admin/post.php?post=124&action=edit",
            "link": "https://wp.example.test/?p=124",
            "warning": "",
            "error": "",
        }

    monkeypatch.setattr(WordPressAdapter, "create_post", fake_create)
    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="wordpress_real",
        mode="publish",
        dry_run=False,
    )

    assert captured["status"] == "draft"
    assert result["status"] == "draft"
    assert "draft" in result["warning"].lower()


def test_no_secret_leak_in_logs_or_response(db, monkeypatch, caplog):
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    password = "never-leak-this-password"
    _mock_wordpress_env(monkeypatch, password=password)
    from lib.publish_sync import sync_page_content

    def fail_request(_self, _method, _url, **_kwargs):
        raise requests.ConnectionError(f"bad credentials: {password}")

    monkeypatch.setattr(requests.Session, "request", fail_request)
    caplog.set_level(logging.WARNING)
    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="wordpress_real",
        dry_run=False,
    )
    logs = models.list_cms_logs(tenant_id=tenant_id, project_id=project_id)

    assert password not in json.dumps(result)
    assert password not in json.dumps(logs)
    assert password not in caplog.text


def test_static_not_modified(monkeypatch):
    before = _tree_digest(ROOT / "static")
    from lib.cms_wordpress import WordPressAdapter

    WordPressAdapter(
        "https://wp.example.test", "api-editor", "secret"
    ).create_post("Title", "<p>Body</p>", dry_run=True)

    assert _tree_digest(ROOT / "static") == before


def test_output_src_not_modified(db, monkeypatch):
    before = _tree_digest(ROOT / "output_src")
    tenant_id, project_id, page_id = _setup_page(db, monkeypatch)
    _mock_wordpress_env(monkeypatch)
    from lib.publish_sync import sync_page_content

    def fail_request(_self, _method, _url, **_kwargs):
        raise requests.ConnectionError("WordPress unavailable")

    monkeypatch.setattr(requests.Session, "request", fail_request)
    result = sync_page_content(
        page_id,
        tenant_id,
        project_id=project_id,
        cms_type="wordpress_real",
        mode="sync",
        dry_run=False,
    )

    assert result["ok"] is False
    assert _tree_digest(ROOT / "output_src") == before
