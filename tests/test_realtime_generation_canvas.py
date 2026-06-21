# -*- coding: utf-8 -*-
"""Phase 9.3.6 realtime generation Canvas contract tests."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest


ROOT = Path(__file__).resolve().parent.parent
RUN_QUERY = urlencode({
    "project": "1",
    "name": "Hammer Hardware Tools Export",
    "seed": "hammer, hardware tools",
    "audience": "wholesalers and distributors",
    "mode": "dry-run",
})


def _tree_digest(path):
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _event_data(stream_text, event_name):
    marker = f"event: {event_name}\n"
    events = []
    for block in stream_text.split("\n\n"):
        if block.startswith(marker):
            for line in block.splitlines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    break
    return events


@pytest.fixture
def realtime_env(monkeypatch, tmp_path):
    import app as app_module
    import auth
    import models
    import run

    workspace = tmp_path / "workspace"
    (workspace / "output_src").mkdir(parents=True)
    monkeypatch.setattr(app_module, "ROOT", workspace)
    monkeypatch.setattr(auth, "current_user", lambda: {"id": 7, "email": "canvas@test.local"})
    monkeypatch.setattr(auth, "current_tenant_id", lambda: 11)
    monkeypatch.setattr(models, "get_project", lambda project_id: {
        "id": int(project_id),
        "user_id": 7,
        "tenant_id": 11,
        "name": "Realtime Canvas",
        "seed_keyword": "hammer hardware tools",
        "industry_config": "",
        "site_url": "",
    })
    monkeypatch.setattr(run.llm, "reset_usage", lambda: None)

    def fake_generation(*_args, progress_callback=None, **_kwargs):
        emit = progress_callback or (lambda *_a, **_k: None)
        emit("stage", {"stage": "generating", "label": "Generating", "message": "One page"})
        emit("progress", {"current": 0, "total": 1, "percent": 0})
        emit("page_start", {
            "slug": "hammer-hardware-tools-supplier",
            "title": "Hammer Hardware Tools Supplier",
            "index": 1,
            "total": 1,
            "status": "generating",
        })
        emit("page_preview", {
            "slug": "hammer-hardware-tools-supplier",
            "title": "Hammer Hardware Tools Supplier",
            "html": "<article><h1>Hammer Hardware Tools Supplier</h1></article>",
            "status": "preview",
        })
        emit("log", {"level": "info", "message": "Preview rendered", "time": "12:00:00"})
        emit("page_done", {
            "slug": "hammer-hardware-tools-supplier",
            "title": "Hammer Hardware Tools Supplier",
            "score": 88,
            "passed": True,
            "status": "done",
        })
        emit("progress", {"current": 1, "total": 1, "percent": 100})
        return {
            "ok": True,
            "pages": [],
            "generation_ids": [55],
            "pages_total": 1,
            "pages_success": 1,
        }

    monkeypatch.setattr(run, "generate_site_from_input", fake_generation)
    app_module.app.config.update(
        TESTING=True,
        RUN_GET_TIMEOUT_SECONDS=1,
        RUN_GET_HEARTBEAT_SECONDS=0.01,
    )
    return app_module, run, workspace


def _stream(realtime_env):
    app_module, _run, _workspace = realtime_env
    with app_module.app.test_client() as client:
        response = client.get(f"/run?{RUN_QUERY}", buffered=False)
        return b"".join(response.response).decode("utf-8")


def test_run_sse_emits_stage_event(realtime_env):
    assert _event_data(_stream(realtime_env), "stage")[0]["stage"] == "generating"


def test_run_sse_emits_progress_event(realtime_env):
    events = _event_data(_stream(realtime_env), "progress")
    assert events[-1]["percent"] == 100


def test_run_sse_emits_page_start_event(realtime_env):
    event = _event_data(_stream(realtime_env), "page_start")[0]
    assert event["slug"] == "hammer-hardware-tools-supplier"


def test_run_sse_emits_page_preview_event(realtime_env):
    event = _event_data(_stream(realtime_env), "page_preview")[0]
    assert "<article>" in event["html"]


def test_run_sse_emits_page_done_event(realtime_env):
    event = _event_data(_stream(realtime_env), "page_done")[0]
    assert event["status"] == "done"


def test_run_sse_emits_log_event(realtime_env):
    assert _event_data(_stream(realtime_env), "log")[0]["message"] == "Preview rendered"


def test_run_sse_keeps_legacy_token_event(realtime_env):
    token = _event_data(_stream(realtime_env), "token")[0]
    assert token["slug"] == "hammer-hardware-tools-supplier"
    assert token["html"].lstrip().lower().startswith("<!doctype html")


def test_run_sse_done_still_works(realtime_env):
    done = _event_data(_stream(realtime_env), "done")[0]
    assert done["ok"] is True
    assert done["index_url"] == "/output/index.html"


def test_run_sse_no_secret_leak(realtime_env, monkeypatch):
    _app_module, run, _workspace = realtime_env
    secret = "sk-never-stream-this-secret"

    def fail_generation(*_args, **_kwargs):
        raise RuntimeError(f"provider failed with {secret}")

    monkeypatch.setattr(run, "generate_site_from_input", fail_generation)
    text = _stream(realtime_env)
    assert secret not in text
    assert "***" in text


def test_template_has_realtime_canvas_hooks():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "data-realtime-canvas" in html


def test_template_has_page_status_list():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "data-page-status-list" in html


def test_template_has_generation_log_panel():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "data-generation-log" in html


def test_output_src_not_modified(realtime_env):
    before = _tree_digest(ROOT / "output_src")
    _stream(realtime_env)
    assert _tree_digest(ROOT / "output_src") == before


def test_static_not_modified(realtime_env):
    before = _tree_digest(ROOT / "static")
    _stream(realtime_env)
    assert _tree_digest(ROOT / "static") == before
