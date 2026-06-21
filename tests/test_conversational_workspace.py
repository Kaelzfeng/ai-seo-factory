# -*- coding: utf-8 -*-
"""Phase 9.3.7 conversational AI workspace contract tests."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import pytest

import models


ROOT = Path(__file__).resolve().parent.parent
CLEAR_INPUT = "铁锤，五金工具，英文 B2B 出口，卖给海外批发商"


def _tree_digest(path):
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _events(stream_text, name):
    marker = f"event: {name}\n"
    found = []
    for block in stream_text.split("\n\n"):
        if not block.startswith(marker):
            continue
        for line in block.splitlines():
            if line.startswith("data: "):
                found.append(json.loads(line[6:]))
                break
    return found


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(path)
    yield conn
    conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def chat_env(db, monkeypatch, tmp_path):
    import app as app_module
    import auth
    import run

    workspace = tmp_path / "workspace"
    (workspace / "output_src").mkdir(parents=True)
    monkeypatch.setattr(app_module, "ROOT", workspace)
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tenant_id = models.create_tenant("conversation-org")
    user_id = models.create_user("conversation@test.local", "h", "s")
    models.add_tenant_member(tenant_id, user_id, role="owner")
    project_id = models.create_project(
        user_id=user_id,
        tenant_id=tenant_id,
        name="Hardware Conversation",
        seed_keyword="hammer hardware tools",
        site_url="https://content.test",
    )
    monkeypatch.setattr(auth, "current_user", lambda: {
        "id": user_id, "email": "conversation@test.local"
    })
    monkeypatch.setattr(auth, "current_tenant_id", lambda: tenant_id)
    monkeypatch.setattr(run.llm, "reset_usage", lambda: None)

    page_specs = [
        ("hammer-hardware-tools-supplier-guide", "Hammer Hardware Tools Supplier Guide", "supplier_guide"),
        ("hammer-manufacturer-wholesale-buyers", "Hammer Manufacturer for Wholesale Buyers", "manufacturer"),
        ("hammer-wholesale-bulk-order-guide", "Hammer Wholesale Bulk Order Guide", "wholesale"),
        ("hammer-export-distributor-guide", "Hammer Export Distributor Guide", "export"),
        ("hammer-specifications-buying-guide", "Hammer Specifications Buying Guide", "specifications"),
        ("hammer-faq-b2b-buyers", "Hammer FAQ for B2B Buyers", "faq"),
    ]

    def fake_generation(*_args, max_pages=None, progress_callback=None, **_kwargs):
        assert max_pages == 6
        emit = progress_callback or (lambda *_a, **_k: None)
        emit("stage", {"stage": "generating", "label": "Generating pages", "message": "Six-page plan"})
        emit("progress", {"current": 0, "total": 6, "percent": 0})
        pages = []
        for index, (slug, title, page_type) in enumerate(page_specs, 1):
            html = f"<article><h1>{title}</h1><p>B2B export content.</p></article>"
            emit("page_start", {
                "index": index, "total": 6, "slug": slug, "title": title,
                "status": "generating",
            })
            emit("page_preview", {
                "slug": slug, "title": title, "html": html, "status": "preview",
            })
            emit("page_done", {
                "slug": slug, "title": title, "url": f"./{slug}.html",
                "score": 90, "passed": True, "status": "done",
            })
            emit("progress", {
                "current": index, "total": 6, "percent": int(index / 6 * 100),
            })
            pages.append({
                "page": {"slug": slug, "type": page_type},
                "content": {"title": title, "html": html},
                "quality": {"score": 90, "passed": True},
            })
        return {
            "ok": True,
            "pages": pages,
            "generation_ids": [101],
            "pages_total": 6,
            "pages_success": 6,
        }

    monkeypatch.setattr(run, "generate_site_from_input", fake_generation)
    app_module.app.config.update(
        TESTING=True,
        CHAT_RUN_TIMEOUT_SECONDS=2,
        CHAT_RUN_HEARTBEAT_SECONDS=0.01,
    )
    return app_module, run, workspace, tenant_id, user_id, project_id


def _chat_stream(chat_env, message=CLEAR_INPUT, project_id=None):
    app_module, _run, _workspace, _tenant_id, _user_id, default_project = chat_env
    query = urlencode({"project_id": project_id or default_project, "message": message})
    with app_module.app.test_client() as client:
        response = client.get(f"/api/chat/run?{query}", buffered=False)
        return response.status_code, b"".join(response.response).decode("utf-8")


def test_chat_run_emits_message_delta(chat_env):
    status, text = _chat_stream(chat_env)
    assert status == 200
    assert _events(text, "message_delta")[0]["role"] == "assistant"


def test_chat_run_emits_intent_locked_for_b2b_hardware(chat_env):
    _status, text = _chat_stream(chat_env)
    intent = _events(text, "intent_locked")[0]
    # Phase 9.3.8: intent_engine uses generic slot extraction with Chinese terms
    assert intent["language"] == "English"
    assert intent.get("product") or intent.get("industry")  # product or industry exists
    assert intent.get("audience")  # audience detected
    assert "hardware" in str(intent.get("industry", "")).lower() or "hammer" in str(intent.get("product", "")).lower()


def test_chat_run_emits_plan_update(chat_env):
    _status, text = _chat_stream(chat_env)
    plan = _events(text, "plan_update")[0]
    assert plan["title"] == "站点生成计划"
    assert len(plan["pages"]) == 6
    assert {page["type"] for page in plan["pages"]} == {
        "supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq"
    }


def test_chat_run_emits_artifact_start(chat_env):
    _status, text = _chat_stream(chat_env)
    artifact = _events(text, "artifact_start")[0]
    assert artifact["artifact_type"] == "website"
    assert artifact["title"]  # title is non-empty


def test_chat_run_emits_artifact_page_events(chat_env):
    _status, text = _chat_stream(chat_env)
    assert len(_events(text, "artifact_page_start")) == 6
    assert len(_events(text, "artifact_page_preview")) == 6
    assert len(_events(text, "artifact_page_done")) == 6


def test_chat_run_emits_final_summary(chat_env):
    _status, text = _chat_stream(chat_env)
    summary = _events(text, "final_summary")[0]
    assert "6" in summary["message"]
    assert "publish_wordpress_draft" in summary["actions"]


def test_b2b_hardware_does_not_trigger_clarification(chat_env):
    _status, text = _chat_stream(chat_env)
    assert not _events(text, "clarification")
    assert "我没太理解" not in text
    assert _events(text, "intent_locked")


def test_clarification_prompt_not_repeated(chat_env):
    _status, first = _chat_stream(chat_env, message="帮我做一个网站")
    _status, second = _chat_stream(chat_env, message="还是帮我做网站")
    first_prompt = _events(first, "message_delta")[-1]["content"]
    second_prompt = _events(second, "message_delta")[-1]["content"]
    assert first_prompt != second_prompt
    assert "我没太理解" not in first_prompt + second_prompt


def test_no_unknown_error_visible_to_user(chat_env):
    _status, text = _chat_stream(chat_env)
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "读取失败：未知错误" not in template
    assert "未知错误" not in text
    assert "关键词数据暂不可用，已使用你的输入继续生成。" in template


def test_default_b2b_generation_has_multiple_pages(chat_env):
    _status, text = _chat_stream(chat_env)
    plan = _events(text, "plan_update")[0]
    assert 4 <= len(plan["pages"]) <= 8
    assert len(plan["pages"]) > 1


def test_final_summary_pages_count_matches_results(chat_env):
    _status, text = _chat_stream(chat_env)
    summary = _events(text, "final_summary")[0]
    done = _events(text, "done")[0]
    assert summary["pages_count"] == done["pages_count"] == len(done["results"]) == 6


def test_done_stops_generating_heartbeat(chat_env):
    _status, text = _chat_stream(chat_env)
    done_index = text.rindex("event: done")
    assert "正在生成中" not in text[done_index:]
    assert text.rstrip().endswith("}")


def test_chat_run_no_secret_leak(chat_env, monkeypatch):
    _app_module, run, *_ = chat_env
    secret = "sk-chat-secret-never-leak"

    def fail_generation(*_args, **_kwargs):
        raise RuntimeError(f"provider rejected {secret}")

    monkeypatch.setattr(run, "generate_site_from_input", fail_generation)
    _status, text = _chat_stream(chat_env)
    assert secret not in text


def test_template_has_gemini_style_chat_stream():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "data-chat-stream" in html
    assert "message_delta" in html
    assert "plan_update" in html
    assert "final_summary" in html


def test_template_has_artifact_canvas():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "data-artifact-canvas" in html
    assert "Artifact · Website" in html


def test_projects_template_opens_conversational_workspace():
    html = (ROOT / "templates" / "projects.html").read_text(encoding="utf-8")
    assert "data-conversational-workspace-link" in html
    assert "进入 AI Workspace" in html


def test_template_has_conversation_state_restore():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "/conversation-state" in html
    assert "restoreConversationState" in html


def test_conversation_state_requires_login(chat_env, monkeypatch):
    app_module, _run, _workspace, _tenant_id, _user_id, project_id = chat_env
    import auth
    monkeypatch.setattr(auth, "current_user", lambda: None)
    with app_module.app.test_client() as client:
        response = client.get(f"/api/projects/{project_id}/conversation-state")
    assert response.status_code == 401


def test_conversation_state_project_isolation(chat_env):
    app_module, _run, _workspace, tenant_id, user_id, _project_id = chat_env
    other_tenant = models.create_tenant("other-conversation-org")
    other_project = models.create_project(
        user_id=user_id, tenant_id=other_tenant,
        name="Other Conversation", seed_keyword="other",
    )
    with app_module.app.test_client() as client:
        response = client.get(f"/api/projects/{other_project}/conversation-state")
    assert response.status_code == 403
    assert tenant_id != other_tenant


def test_conversation_state_empty_ok(chat_env):
    app_module, _run, _workspace, tenant_id, user_id, _project_id = chat_env
    empty_project = models.create_project(
        user_id=user_id, tenant_id=tenant_id,
        name="Empty Conversation", seed_keyword="empty",
    )
    with app_module.app.test_client() as client:
        payload = client.get(
            f"/api/projects/{empty_project}/conversation-state"
        ).get_json()
    assert payload["ok"] is True
    assert payload["messages"] == []
    assert payload["artifact"]["pages"] == []


def test_conversation_state_restores_messages_and_artifact(chat_env):
    app_module, _run, _workspace, _tenant_id, _user_id, project_id = chat_env
    _chat_stream(chat_env)
    with app_module.app.test_client() as client:
        payload = client.get(
            f"/api/projects/{project_id}/conversation-state"
        ).get_json()
    assert payload["messages"][0] == {"role": "user", "content": CLEAR_INPUT}
    assert any(message["role"] == "assistant" for message in payload["messages"])
    assert len(payload["plan"]["pages"]) == 6
    assert len(payload["artifact"]["pages"]) == 6
    assert payload["artifact"]["preview"]["slug"]  # preview slug exists
    assert "faq" in payload["artifact"]["preview"]["slug"]  # FAQ page is last


def test_wordpress_button_disabled_until_done():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="artifactWpBtn"' in html
    assert 'id="artifactWpBtn"' in html and "disabled" in html[html.index('id="artifactWpBtn"'):html.index('id="artifactWpBtn"') + 300]
    assert "enableArtifactActions" in html


def test_output_src_not_modified(chat_env):
    before = _tree_digest(ROOT / "output_src")
    _chat_stream(chat_env)
    assert _tree_digest(ROOT / "output_src") == before


def test_static_not_modified(chat_env):
    before = _tree_digest(ROOT / "static")
    _chat_stream(chat_env)
    assert _tree_digest(ROOT / "static") == before
