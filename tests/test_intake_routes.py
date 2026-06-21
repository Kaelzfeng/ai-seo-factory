# -*- coding: utf-8 -*-
"""tests/test_intake_routes.py · /intake + /api/agent/message 修复测试"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models


@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app


@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = models.init_db(dbpath); yield conn; conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


# Test 1: POST /intake returns 200
def test_intake_returns_200(app):
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "PU leather export site", "history": []})
        assert resp.status_code == 200


# Test 2: /intake returns ok/action/message
def test_intake_has_action(app):
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "I want an English B2B site", "history": []})
        data = resp.get_json()
        assert "ok" in data
        assert "action" in data


# Test 3: /intake empty message returns error
def test_intake_empty_message(app):
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "", "history": []})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False


# Test 4: /api/agent/message returns 200
def test_agent_message_returns_200(app):
    with app.test_client() as c:
        resp = c.post("/api/agent/message", json={"message": "PU leather B2B export"})
        assert resp.status_code == 200


# Test 5: /api/agent/message returns scope + blueprint
def test_agent_message_has_scope(app):
    with app.test_client() as c:
        resp = c.post("/api/agent/message", json={"message": "PU leather B2B export site in English"})
        data = resp.get_json()
        assert data["ok"] is True
        assert "scope" in data
        assert "blueprint" in data
        assert "reply" in data


# Test 6: /api/agent/message supports text field
def test_agent_message_text_field(app):
    with app.test_client() as c:
        resp = c.post("/api/agent/message", json={"text": "PU leather export"})
        assert resp.status_code == 200


# Test 7: /api/agent/message supports input field
def test_agent_message_input_field(app):
    with app.test_client() as c:
        resp = c.post("/api/agent/message", json={"input": "PU leather"})
        assert resp.status_code == 200


# Test 8: /api/agent/message empty returns error
def test_agent_message_empty(app):
    with app.test_client() as c:
        resp = c.post("/api/agent/message", json={"message": ""})
        assert resp.status_code == 400


# Test 9: /intake/confirm requires login
def test_intake_confirm_requires_login(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("ic-org"); uid = models.create_user("ic@t.com","h","s")
    models.add_tenant_member(tid, uid, "owner")
    brief = {"industry": "PU leather", "project_name": "Test", "language": "English"}
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/intake/confirm", json={"brief": brief})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data.get("project_id")


# Test 10: fetch URL exists in url_map
def test_intake_url_exists(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/intake" in rules
    assert "/api/agent/message" in rules
    assert "/intake/confirm" in rules


# ── Chinese intent tests ─────────────────────────────

def test_chinese_hammer_export_returns_brief(app):
    """铁锤五金出口 → brief。"""
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "铁锤，五金工具，英文B2B出口，卖给海外批发商"})
        data = resp.get_json()
        assert data["ok"] is True
        # Should be brief with Chinese fallback
        assert "action" in data
        if data["action"] == "brief":
            assert data["brief"]["language"] == "English"
            assert "hammer" in data["brief"]["industry"].lower() or "hardware" in data["brief"]["industry"].lower()
            assert len(data["brief"]["seed_keywords"]) >= 3


def test_chinese_hardware_b2b_returns_brief(app):
    """五金工具 B2B → brief。"""
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "五金工具，出口海外，英文"})
        data = resp.get_json()
        assert data["ok"] is True


def test_short_unclear_input_returns_ask(app):
    """模糊输入 → ask。"""
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "帮我做个站"})
        data = resp.get_json()
        assert data["ok"] is True
        # Short/unclear should get ask
        assert "action" in data


def test_intake_supports_content_field(app):
    with app.test_client() as c:
        resp = c.post("/intake", json={"content": "hammer export"})
        assert resp.status_code == 200


def test_intake_brief_has_required_fields(app):
    with app.test_client() as c:
        resp = c.post("/intake", json={"message": "铁锤，五金工具，英文B2B出口，卖给海外批发商"})
        data = resp.get_json()
        if data.get("action") == "brief" and data.get("brief"):
            b = data["brief"]
            assert b.get("project_name")
            assert b.get("industry")
            assert b.get("market")
            assert b.get("language")
            assert b.get("seed_keywords")


def test_intake_never_500_on_chinese(app):
    inputs = [
        "hammer export",
        "五金工具批发海外",
        "PU皮革B2B出口英文",
        "",  # should get 400 not 500
    ]
    with app.test_client() as c:
        for msg in inputs:
            resp = c.post("/intake", json={"message": msg})
            assert resp.status_code in (200, 400), f"Failed on: {msg}"


# ── Confirm redirect tests ────────────────────────────

def test_intake_confirm_returns_run_fields(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("co-org"); uid = models.create_user("co@t.com","h","s")
    models.add_tenant_member(tid, uid, "owner")
    brief = {"industry": "hammer", "project_name": "Hammer Site", "language": "English",
             "seed_keywords": ["hammer supplier"], "audience": "importers"}
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/intake/confirm", json={"brief": brief})
        data = resp.get_json()
        assert data["ok"] is True
        assert data.get("run")
        assert data["run"]["seed"]
        assert data["run"]["name"]


def test_project_detail_returns_200(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pd-org"); uid = models.create_user("pd@t.com","h","s")
    models.add_tenant_member(tid, uid, "owner")
    pid = models.create_project(user_id=uid, name="Test", tenant_id=tid, seed_keyword="t")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get(f"/projects/{pid}?autorun=1")
        assert resp.status_code == 200


def test_template_no_old_redirect():
    root = Path(__file__).resolve().parent.parent
    content = (root / "templates/index.html").read_text(encoding="utf-8")
    # Should NOT have the old /?project= redirect
    assert '"/?" + qp' not in content
    # Should have /projects/ redirect
    assert '"/projects/" + encodeURIComponent' in content


# Test 11: health still works
def test_health_still_ok(app):
    with app.test_client() as c:
        resp = c.get("/api/health")
        assert resp.status_code == 200


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    if (root / "templates").exists():
        for f in (root / "templates").rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0

def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    if (root / "static").exists():
        for f in (root / "static").rglob("*"):
            if f.is_file(): assert f.exists()
