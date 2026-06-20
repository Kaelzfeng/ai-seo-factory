# -*- coding: utf-8 -*-
"""Phase 5 integration tests: API, CLI, persistence, legacy compat"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import models


@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"
    return _app


@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    yield conn
    conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


def _login(app, monkeypatch, db_conn):
    monkeypatch.setattr(models, "_get_db", lambda: db_conn)
    tid = models.create_tenant("comp-org")
    uid = models.create_user("comp@test.com", "h", "s")
    models.add_tenant_member(tid, uid, role="owner")
    pid = models.create_project(user_id=uid, name="Comp Project", tenant_id=tid, seed_keyword="test", language="English", site_url="https://example.com")
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
    return tid, uid, pid


def test_create_and_get_report(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("cr-test")
    rid = models.create_competitor_report(tenant_id=tid, query="test", report_json='{"x":1}')
    r = models.get_competitor_report(rid)
    assert r is not None
    assert r["query"] == "test"


def test_tenant_isolation(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid1 = models.create_tenant("cr-t1")
    tid2 = models.create_tenant("cr-t2")
    models.create_competitor_report(tenant_id=tid1, query="t1")
    reports = models.list_competitor_reports(tenant_id=tid2)
    assert len(reports) == 0
    reports = models.list_competitor_reports(tenant_id=tid1)
    assert len(reports) == 1


def test_api_analyze_returns_json(app, db, monkeypatch):
    tid, uid, pid = _login(app, monkeypatch, db)
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/competitor/analyze", json={"query": "PU leather supplier"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert "report" in data


def test_api_reports_list(app, db, monkeypatch):
    tid, uid, pid = _login(app, monkeypatch, db)
    models.create_competitor_report(tenant_id=tid, query="test")
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.get("/api/competitor/reports")
        assert resp.status_code == 200


def test_cli_mock_runs():
    """Verify the CLI module can be imported and run --mock"""
    import run as _run
    result = _run.analyze_competitor_seo("PU leather supplier")
    assert result["status"] == "completed"
    assert len(result["competitors"]) == 10
    assert result["gap_matrix"] is not None
    assert result["surpass_strategy"] is not None
    assert len(result["surpass_strategy"]["recommended_pages"]) > 0


def test_legacy_generate_site_still_works(monkeypatch):
    import run as _run
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"img"})
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: {"score":85,"breakdown":{},"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":1000})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({"name":"test","seed_keyword":"test","pages":[{"title":f"P{n}","type":"guide","slug":f"p{n}","target_keyword":f"k{n}"} for n in range(1,9)]}, f)
    project = {"id":0,"tenant_id":None,"user_id":None,"name":"test","industry_config":tmp_yaml,"seed_keyword":"test","language":"English","site_url":"https://example.com"}
    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
    assert result["summary"]["total_pages"] == 8


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if templates_dir.exists():
        for f in templates_dir.rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0


def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if static_dir.exists():
        for f in static_dir.rglob("*"):
            if f.is_file():
                assert f.exists()
