# -*- coding: utf-8 -*-
"""Phase 9.3.6 persisted preview restore contract tests."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

import models


ROOT = Path(__file__).resolve().parent.parent


def _tree_digest(path):
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


@pytest.fixture
def preview_env(db, monkeypatch):
    import app as app_module
    import auth

    monkeypatch.setattr(models, "_get_db", lambda: db)
    tenant_id = models.create_tenant("preview-state-org")
    user_id = models.create_user("preview-state@test.local", "h", "s")
    models.add_tenant_member(tenant_id, user_id, role="owner")
    project_id = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="Preview State Project",
        seed_keyword="hardware tools supplier",
        site_url="https://content.test",
    )
    monkeypatch.setattr(auth, "current_user", lambda: {
        "id": user_id, "email": "preview-state@test.local"
    })
    monkeypatch.setattr(auth, "current_tenant_id", lambda: tenant_id)
    app_module.app.config.update(TESTING=True, SECRET_KEY="preview-test-secret")
    return app_module, tenant_id, user_id, project_id


def test_configs_route_returns_json(preview_env):
    app_module, *_ = preview_env
    with app_module.app.test_client() as client:
        response = client.get("/configs")
    assert response.status_code == 200
    assert response.is_json
    assert isinstance(response.get_json(), list)


def test_configs_route_no_secret_leak(preview_env, monkeypatch):
    app_module, *_ = preview_env
    secrets = {
        "OPENAI_API_KEY": "sk-config-route-secret",
        "WP_APP_PASSWORD": "wp-config-route-secret",
        "SECRET_KEY": "flask-config-route-secret",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    with app_module.app.test_client() as client:
        text = client.get("/configs").get_data(as_text=True)
        text += client.get("/themes").get_data(as_text=True)
    for value in secrets.values():
        assert value not in text


def test_themes_route_returns_json(preview_env):
    app_module, *_ = preview_env
    with app_module.app.test_client() as client:
        response = client.get("/themes")
    assert response.status_code == 200
    assert response.is_json
    themes = response.get_json()
    assert isinstance(themes, list)
    assert any(theme["name"] == "atelier-dark" for theme in themes)


def test_preview_state_requires_login(preview_env, monkeypatch):
    app_module, _tenant_id, _user_id, project_id = preview_env
    import auth
    monkeypatch.setattr(auth, "current_user", lambda: None)
    with app_module.app.test_client() as client:
        response = client.get(f"/api/projects/{project_id}/preview-state")
    assert response.status_code == 401


def test_preview_state_project_tenant_isolation(preview_env):
    app_module, tenant_id, user_id, _project_id = preview_env
    other_tenant = models.create_tenant("other-preview-org")
    other_project = models.create_project(
        user_id=user_id,
        tenant_id=other_tenant,
        name="Other Tenant Project",
        seed_keyword="other",
    )
    with app_module.app.test_client() as client:
        response = client.get(f"/api/projects/{other_project}/preview-state")
    assert response.status_code == 403
    assert response.get_json()["ok"] is False
    assert tenant_id != other_tenant


def test_preview_state_empty_ok(preview_env):
    app_module, _tenant_id, _user_id, project_id = preview_env
    with app_module.app.test_client() as client:
        response = client.get(f"/api/projects/{project_id}/preview-state")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["preview"] is None
    assert payload["pages"] == []


def test_preview_state_returns_latest_page(preview_env):
    app_module, tenant_id, _user_id, project_id = preview_env
    models.create_page_content(
        tenant_id=tenant_id,
        project_id=project_id,
        slug="older-page",
        title="Older Page",
        gutenberg_html="<article><h1>Older Page</h1></article>",
        quality_score=70,
        review_status="passed",
    )
    models.create_page_content(
        tenant_id=tenant_id,
        project_id=project_id,
        slug="latest-page",
        title="Latest Hardware Supplier Page",
        gutenberg_html="<article><h1>Latest Hardware Supplier Page</h1></article>",
        quality_score=91,
        review_status="passed",
    )
    with app_module.app.test_client() as client:
        payload = client.get(
            f"/api/projects/{project_id}/preview-state"
        ).get_json()
    assert payload["preview"]["slug"] == "latest-page"
    assert "Latest Hardware Supplier Page" in payload["preview"]["html"]
    assert [page["slug"] for page in payload["pages"]] == ["older-page", "latest-page"]


def test_preview_state_latest_generation_is_project_scoped(preview_env):
    app_module, tenant_id, user_id, project_id = preview_env
    own_generation = models.create_generation(
        project_id, tenant_id=tenant_id, status="completed", title="Own Generation"
    )
    other_project = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="Same Tenant Other Project",
        seed_keyword="other project",
    )
    models.create_generation(
        other_project, tenant_id=tenant_id, status="completed", title="Other Generation"
    )
    with app_module.app.test_client() as client:
        payload = client.get(
            f"/api/projects/{project_id}/preview-state"
        ).get_json()
    assert payload["latest_generation"]["id"] == own_generation


def test_preview_state_no_secret_leak(preview_env):
    app_module, tenant_id, _user_id, project_id = preview_env
    secret = "sk-preview-state-must-not-leak"
    models.create_generation(
        project_id,
        tenant_id=tenant_id,
        status="failed",
        result_json=json.dumps({"error": f"provider rejected {secret}"}),
    )
    with app_module.app.test_client() as client:
        text = client.get(
            f"/api/projects/{project_id}/preview-state"
        ).get_data(as_text=True)
    assert secret not in text
    assert "result_json" not in text


def test_project_template_fetches_preview_state():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "/preview-state" in html
    assert "restorePreviewState" in html


def test_refresh_restore_does_not_call_run():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    start = html.index("function restorePreviewState")
    end = html.find("\n  function ", start + 20)
    function_body = html[start:end if end != -1 else len(html)]
    assert "/preview-state" in function_body
    assert "beginStream(" not in function_body
    assert 'fetch("/run' not in function_body


def test_output_src_not_modified(preview_env):
    app_module, _tenant_id, _user_id, project_id = preview_env
    before = _tree_digest(ROOT / "output_src")
    with app_module.app.test_client() as client:
        client.get(f"/api/projects/{project_id}/preview-state")
    assert _tree_digest(ROOT / "output_src") == before


def test_static_not_modified(preview_env):
    app_module, _tenant_id, _user_id, project_id = preview_env
    before = _tree_digest(ROOT / "static")
    with app_module.app.test_client() as client:
        client.get(f"/api/projects/{project_id}/preview-state")
    assert _tree_digest(ROOT / "static") == before
