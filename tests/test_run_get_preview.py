# -*- coding: utf-8 -*-
"""Regression coverage for the real GET /run SSE preview path."""

import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest


ROOT = Path(__file__).resolve().parent.parent
PREVIEW_SLUG = "hammer-hardware-tools-supplier"
PREVIEW_FILE = f"{PREVIEW_SLUG}.html"
RUN_QUERY = urlencode({
    "project": "1",
    "name": "Hammer Hardware Tools Export",
    "seed": "hammer, hardware tools",
    "audience": "wholesalers and distributors",
    "mode": "dry-run",
})


def _event_data(stream_text, event_name):
    marker = f"event: {event_name}\n"
    for block in stream_text.split("\n\n"):
        if block.startswith(marker):
            for line in block.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])
    raise AssertionError(f"Missing SSE event: {event_name}\n{stream_text}")


@pytest.fixture
def run_get_env(monkeypatch, tmp_path):
    import app as app_module
    import auth
    import models
    import run

    workspace = tmp_path / "workspace"
    (workspace / "output_src").mkdir(parents=True)
    monkeypatch.setattr(app_module, "ROOT", workspace)
    monkeypatch.setattr(auth, "current_user", lambda: {"id": 7, "email": "preview@test.local"})
    monkeypatch.setattr(auth, "current_tenant_id", lambda: 11)
    monkeypatch.setattr(models, "get_project", lambda project_id: {
        "id": int(project_id),
        "user_id": 7,
        "tenant_id": 11,
        "name": "Untitled Project",
        "seed_keyword": "",
        "industry_config": "",
        "site_url": "",
    })
    monkeypatch.setattr(run.llm, "reset_usage", lambda: None)
    app_module.app.config.update(
        TESTING=True,
        RUN_GET_TIMEOUT_SECONDS=0.05,
        RUN_GET_HEARTBEAT_SECONDS=0.01,
    )
    return app_module, run, workspace


def _open_run(client):
    return client.get(f"/run?{RUN_QUERY}", buffered=False)


def test_run_get_emits_preview_within_first_seconds(run_get_env, monkeypatch):
    app_module, run, _workspace = run_get_env
    monkeypatch.setattr(
        run, "generate_site_from_input",
        lambda *args, **kwargs: (time.sleep(0.2) or {"ok": True, "pages": []}),
    )

    started = time.monotonic()
    with app_module.app.test_client() as client:
        response = _open_run(client)
        stream_text = b"".join(response.response).decode("utf-8")

    assert time.monotonic() - started < 3
    assert stream_text.index("event: token") < stream_text.index("event: done")
    token = _event_data(stream_text, "token")
    assert token["slug"] == PREVIEW_SLUG
    assert token["html"].lstrip().lower().startswith("<!doctype html")


def test_run_get_generates_index_html_immediately(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        assert (workspace / "output_src" / "index.html").is_file()
        b"".join(response.response)
        assert client.get("/output/index.html").status_code == 200


def test_run_get_generates_preview_page_html(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        page = workspace / "output_src" / PREVIEW_FILE
        assert page.is_file()
        b"".join(response.response)
        assert client.get(f"/output/{PREVIEW_FILE}").status_code == 200


def test_preview_contains_hardware_terms(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        html = (workspace / "output_src" / PREVIEW_FILE).read_text(encoding="utf-8").lower()
        b"".join(response.response)

    for term in (
        "hammer", "hardware tools", "supplier", "manufacturer", "wholesale",
        "export", "b2b export", "wholesalers and distributors",
    ):
        assert term in html


def test_preview_not_test_page_title(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        html = (workspace / "output_src" / PREVIEW_FILE).read_text(encoding="utf-8").lower()
        b"".join(response.response)

    for forbidden in (
        "test page title", "batch test page", "test paragraph", "pu leather",
        "synthetic leather", "example.com",
    ):
        assert forbidden not in html


def test_run_get_timeout_returns_preview_done(run_get_env, monkeypatch):
    app_module, run, _workspace = run_get_env

    def slow_generation(*args, **kwargs):
        time.sleep(0.2)
        return {"ok": True, "pages": []}

    monkeypatch.setattr(run, "generate_site_from_input", slow_generation)
    with app_module.app.test_client() as client:
        started = time.monotonic()
        response = _open_run(client)
        stream_text = b"".join(response.response).decode("utf-8")
        elapsed = time.monotonic() - started

    done = _event_data(stream_text, "done")
    assert elapsed < 0.15
    assert done["ok"] is True
    assert done["warning"] == "LLM generation timed out, preview content was generated from seed terms."
    assert done["index_url"] == "/output/index.html"


def test_done_results_match_preview_html(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        stream_text = b"".join(response.response).decode("utf-8")

    done = _event_data(stream_text, "done")
    assert done["results"] == [{
        "slug": PREVIEW_SLUG,
        "title": "Hammer Hardware Tools Supplier",
        "type": "page",
        "score": None,
        "passed": True,
        "link": f"./{PREVIEW_FILE}",
    }]
    assert (workspace / "output_src" / PREVIEW_FILE).is_file()


def test_output_src_not_used_as_input(run_get_env, monkeypatch):
    app_module, run, workspace = run_get_env
    poisoned = workspace / "output_src" / "old-result.json"
    poisoned.write_text(json.dumps({
        "title": "Test Page Title",
        "html": "<p>pu leather synthetic leather example.com</p>",
    }), encoding="utf-8")
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        token = _event_data(b"".join(response.response).decode("utf-8"), "token")

    assert not poisoned.exists()
    lowered = token["html"].lower()
    assert "test page title" not in lowered
    assert "pu leather" not in lowered
    assert "example.com" not in lowered


def test_post_run_still_works(run_get_env, monkeypatch):
    app_module, run, _workspace = run_get_env
    calls = []

    def fake_generate(project, mode="dry-run", **kwargs):
        calls.append((project["id"], mode))
        return {"ok": True, "pages": []}

    monkeypatch.setattr(run, "generate_site", fake_generate)
    with app_module.app.test_client() as client:
        response = client.post("/run", json={"project_id": 1, "mode": "dry-run"})

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert calls == [(1, "dry-run")]


def test_preview_uses_atelier_renderer(monkeypatch):
    import app as app_module
    from lib.themes import atelier

    captured = {}
    original = atelier.render_page

    def spy(ctx):
        captured.update(ctx)
        return original(ctx)

    monkeypatch.setattr(atelier, "render_page", spy)
    html = app_module._render_run_preview_html(
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    )

    assert captured["title"] == "Hammer Hardware Tools Supplier"
    assert captured["type_label"] == "Supplier Guide"
    assert captured["body_has_h1"] is True
    assert captured["robots"] == "noindex,follow"
    assert '<header class="top">' in html


def test_preview_html_not_bare_main_only():
    import app as app_module

    html = app_module._render_run_preview_html(
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    ).lower()

    assert "<body><main>" not in html
    assert "<style>" in html
    assert '<header class="top">' in html


def test_preview_html_has_hero_article_footer():
    import app as app_module

    html = app_module._render_run_preview_html(
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    ).lower()

    assert 'class="hero"' in html
    assert "<article>" in html
    assert '<footer class="site">' in html


def test_preview_index_uses_atelier_renderer(monkeypatch, tmp_path):
    import app as app_module
    from lib.themes import atelier

    captured = {}
    original = atelier.render_index

    def spy(ctx):
        captured.update(ctx)
        return original(ctx)

    monkeypatch.setattr(atelier, "render_index", spy)
    app_module._write_run_preview_index(
        tmp_path,
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    )
    html = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert captured["site_name"] == "Hammer Hardware Tools Export"
    assert captured["groups"][0]["label"] == "Supplier Guides"
    assert captured["groups"][0]["items"][0]["type_label"] == "Supplier Guide"
    assert '<header class="top">' in html
    assert 'class="hero"' in html
    assert "<article>" in html
    assert '<footer class="site">' in html


def test_sse_token_contains_rendered_preview_html(run_get_env, monkeypatch):
    app_module, run, _workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        token = _event_data(b"".join(response.response).decode("utf-8"), "token")

    html = token["html"].lower()
    assert '<header class="top">' in html
    assert 'class="hero"' in html
    assert "<article>" in html
    assert '<footer class="site">' in html


def test_preview_not_pu_leather_or_mock_snippet(tmp_path):
    import app as app_module

    page_html = app_module._render_run_preview_html(
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    )
    app_module._write_run_preview_index(
        tmp_path,
        "Hammer Hardware Tools Export",
        "hammer, hardware tools",
        "wholesalers and distributors",
    )
    index_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    combined = f"{page_html}\n{index_html}".lower()

    for forbidden in (
        "pu leather", "synthetic leather", "mock snippet", "example.com",
        "test page title", "batch test page",
    ):
        assert forbidden not in combined


def test_output_routes_work(run_get_env, monkeypatch):
    app_module, run, _workspace = run_get_env
    monkeypatch.setattr(run, "generate_site_from_input", lambda *args, **kwargs: {"ok": True, "pages": []})

    with app_module.app.test_client() as client:
        response = _open_run(client)
        b"".join(response.response)
        index_response = client.get("/output/index.html")
        page_response = client.get(f"/output/{PREVIEW_FILE}")

    assert index_response.status_code == 200
    assert page_response.status_code == 200
    for body in (index_response.get_data(as_text=True), page_response.get_data(as_text=True)):
        assert 'class="hero"' in body
        assert "<article>" in body
        assert '<footer class="site">' in body


def test_static_not_modified():
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "static"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""


def test_templates_no_mojibake():
    mojibake_markers = ("\ufffd", "锟斤拷", "鈹€", "Ã", "Â", "â€")
    for path in (ROOT / "templates").rglob("*.html"):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert hashlib.sha256(raw).hexdigest()
        assert not any(marker in text for marker in mojibake_markers), path
