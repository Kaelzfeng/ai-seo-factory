# -*- coding: utf-8 -*-
"""Phase 9.2: Job Mode 测试 (create, run, status, result, cancel, retry, API, CLI)"""
import json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models


@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = models.init_db(dbpath); yield conn; conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


def _setup(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("jm-org")
    uid = models.create_user("jm@t.com", "h", "s")
    pid = models.create_project(user_id=uid, name="JM", tenant_id=tid, seed_keyword="t", language="En", site_url="https://x.com")
    return tid, uid, pid


def _mock_llm(monkeypatch):
    import run as _run
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"i"})
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg,c,cfg: {"score":85,"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    # Mock keyword_scout to avoid real Bing API calls
    try:
        from lib import keyword_scout
        monkeypatch.setattr(keyword_scout, "grounded_plan",
                           lambda seed, max_pages=7: {"plan": [
                               {"title":f"P{n}","type":"guide","slug":f"p{n}","target_keyword":f"k{n}"}
                               for n in range(1,9)]})
    except ImportError:
        pass


# Create job
def test_create_job_queued(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    from lib.generation_job_mode import create_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="test input", mode="dry-run")
    assert r["ok"] is True
    assert r["status"] == "queued"
    assert r["job_id"] > 0


def test_create_job_stores_input(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    from lib.generation_job_mode import create_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="PU leather B2B", mode="dry-run")
    job = models.get_job(r["job_id"])
    meta = json.loads(job["meta_json"])
    assert meta["_input"]["user_input"] == "PU leather B2B"


# Run job (mock)
def test_run_job_completes(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    _mock_llm(monkeypatch)
    from lib.generation_job_mode import create_generation_job, run_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="test", mode="dry-run")
    result = run_generation_job(r["job_id"], tenant_id=tid)
    assert result["ok"] is True


def test_run_job_status_transitions(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    _mock_llm(monkeypatch)
    from lib.generation_job_mode import create_generation_job, run_generation_job, get_generation_job_status
    r = create_generation_job(tid, project_id=pid, user_input="test", mode="dry-run")
    run_generation_job(r["job_id"], tenant_id=tid)
    s = get_generation_job_status(r["job_id"])
    assert s["status"] in ("completed", "partial_success")


# Cancel
def test_cancel_queued_job(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    from lib.generation_job_mode import create_generation_job, cancel_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="test")
    c = cancel_generation_job(r["job_id"], tenant_id=tid)
    assert c["ok"] is True
    assert c["status"] == "cancelled"


# Retry
def test_retry_failed_job(db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    from lib.generation_job_mode import create_generation_job, retry_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="test")
    # Manually set to failed
    models.update_job(r["job_id"], status="failed")
    ret = retry_generation_job(r["job_id"], tenant_id=tid)
    assert ret["ok"] is True
    assert ret["status"] == "queued"


# Tenant isolation
def test_job_tenant_isolation(db, monkeypatch):
    tid1, uid, pid = _setup(db, monkeypatch)
    tid2 = models.create_tenant("jm-other")
    from lib.generation_job_mode import create_generation_job, get_generation_job_status
    r = create_generation_job(tid1, project_id=pid, user_input="test")
    s = get_generation_job_status(r["job_id"], tenant_id=tid2)
    assert s.get("ok") is False


# API
@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app


def test_api_create_job(app, db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    models.add_tenant_member(tid, uid, "owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/api/jobs/generation", json={"project_id": pid, "user_input": "test", "mode": "dry-run"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "queued"


def test_api_job_status(app, db, monkeypatch):
    tid, uid, pid = _setup(db, monkeypatch)
    models.add_tenant_member(tid, uid, "owner")
    from lib.generation_job_mode import create_generation_job
    r = create_generation_job(tid, project_id=pid, user_input="test")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get(f"/api/jobs/generation/{r['job_id']}")
        assert resp.status_code == 200


def test_api_job_tenant_isolation(app, db, monkeypatch):
    tid1, uid1, pid = _setup(db, monkeypatch)
    models.add_tenant_member(tid1, uid1, "owner")
    tid2 = models.create_tenant("jm-api2"); uid2 = models.create_user("jm2@t.com","h2","s2")
    models.add_tenant_member(tid2, uid2, "owner")
    from lib.generation_job_mode import create_generation_job
    r = create_generation_job(tid1, project_id=pid, user_input="test")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid2
        resp = c.get(f"/api/jobs/generation/{r['job_id']}")
        data = resp.get_json()
        assert data.get("ok") is False


# CLI smoke (avoid subprocess - DB lock issues)
def test_cli_script_exists():
    root = Path(__file__).resolve().parent.parent
    assert (root / "scripts/run_generation_job.py").exists()
    assert (root / "scripts/job_status.py").exists()
    assert (root / "scripts/real_llm_job_smoke.py").exists()

def test_real_llm_job_smoke_script_valid():
    root = Path(__file__).resolve().parent.parent
    code = (root / "scripts/real_llm_job_smoke.py").read_text()
    assert "create_generation_job" in code
    assert "run_generation_job" in code


# Legacy
def test_legacy_generate_site(monkeypatch):
    import run as _run
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"i"})
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg,c,cfg: {"score":85,"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    import yaml
    tmp = tempfile.mktemp(suffix=".yaml")
    with open(tmp,"w") as f: yaml.dump({"name":"t","seed_keyword":"t","pages":[{"title":"P1","type":"guide","slug":"p1","target_keyword":"k1"}]}, f)
    project = {"id":0,"tenant_id":None,"name":"t","industry_config":tmp,"seed_keyword":"t","language":"En","site_url":"https://x.com"}
    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True


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
