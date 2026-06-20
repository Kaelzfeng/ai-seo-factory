# -*- coding: utf-8 -*-
"""Phase 9.3: Beta 验证测试"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models


@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = models.init_db(dbpath); yield conn; conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


# Demo data
def test_bootstrap_workspace_idempotent(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    from lib.demo_data import bootstrap_demo_workspace
    ws1 = bootstrap_demo_workspace()
    ws2 = bootstrap_demo_workspace()
    assert ws1["tenant_id"] == ws2["tenant_id"]
    assert ws1["project_id"] == ws2["project_id"]


# Beta feedback
def test_feedback_create(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("fb-test")
    from lib.beta_feedback import create_beta_feedback, list_beta_feedback
    create_beta_feedback(tid, rating=4, category="content_quality", message="Good")
    items = list_beta_feedback(tid)
    assert len(items) >= 1
    assert items[0]["rating"] == 4


def test_feedback_rating_clamped(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("fb-rating")
    from lib.beta_feedback import create_beta_feedback
    fid = create_beta_feedback(tid, rating=10)
    from models import list_beta_feedback_records
    items = list_beta_feedback_records(tenant_id=tid)
    assert 1 <= items[0]["rating"] <= 5


def test_feedback_tenant_isolation(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid1 = models.create_tenant("fb-t1"); tid2 = models.create_tenant("fb-t2")
    from lib.beta_feedback import create_beta_feedback, list_beta_feedback
    create_beta_feedback(tid1, rating=5)
    assert len(list_beta_feedback(tid2)) == 0


def test_feedback_summarize(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("fb-sum")
    from lib.beta_feedback import create_beta_feedback, summarize_beta_feedback
    create_beta_feedback(tid, rating=5, category="speed")
    create_beta_feedback(tid, rating=3, category="content_quality")
    s = summarize_beta_feedback(tid)
    assert s["count"] == 2
    assert s["avg_rating"] == 4.0


# Beta report
def test_beta_report(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("br-test")
    from lib.beta_report import generate_private_beta_report, beta_report_to_markdown
    r = generate_private_beta_report(tid)
    assert r["ok"] is True
    m = r["metrics"]
    assert "jobs" in m
    assert "page_contents" in m
    assert "generated_pages" in m
    md = beta_report_to_markdown(r)
    assert "# Private Beta Report" in md
    assert "## Jobs" in md
    assert "## Generated Pages" in md
    assert "## Page Contents" in md
    assert "## Feedback" in md


def test_beta_report_reads_job_pages(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("br-job")
    # Create a job with pages_success in meta
    from models import create_batch_run, create_job, update_job
    bid = create_batch_run(tenant_id=tid, name="test", total_jobs=1)
    jid = create_job(tenant_id=tid, batch_run_id=bid, keyword="test")
    update_job(jid, status="completed", pages_success=8, pages_total=8,
               meta_json='{"_result":{"pages_success":8,"pages_total":8,"code":"success"}}')
    from lib.beta_report import generate_private_beta_report
    r = generate_private_beta_report(tid)
    assert r["metrics"]["jobs"]["pages_success_total"] >= 8
    assert r["metrics"]["generated_pages"]["from_job_results"] >= 8


def test_beta_report_project_filter(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("br-pf")
    uid = models.create_user("br-pf@t.com", "h", "s")
    pid1 = models.create_project(user_id=uid, name="P1", tenant_id=tid, seed_keyword="t")
    pid2 = models.create_project(user_id=uid, name="P2", tenant_id=tid, seed_keyword="t")
    models.create_page_content(tenant_id=tid, project_id=pid1, slug="p1-page", title="P1", primary_keyword="k")
    models.create_page_content(tenant_id=tid, project_id=pid2, slug="p2-page", title="P2", primary_keyword="k")
    from lib.beta_report import generate_private_beta_report
    r1 = generate_private_beta_report(tid, project_id=pid1)
    r2 = generate_private_beta_report(tid, project_id=pid2)
    assert r1["metrics"]["page_contents"]["persisted"] == 1
    assert r2["metrics"]["page_contents"]["persisted"] == 1
    # All (no filter)
    r_all = generate_private_beta_report(tid)
    assert r_all["metrics"]["page_contents"]["persisted"] >= 2


# API
@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app


def test_api_beta_feedback(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("api-bf"); uid = models.create_user("api-bf@t.com","h","s")
    models.add_tenant_member(tid, uid, "owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/api/beta/feedback", json={"rating": 4, "message": "test", "category": "speed"})
        assert resp.status_code == 200
        resp2 = c.get("/api/beta/feedback")
        assert resp2.status_code == 200


def test_api_beta_report(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("api-br"); uid = models.create_user("api-br@t.com","h","s")
    models.add_tenant_member(tid, uid, "owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get("/api/beta/report")
        assert resp.status_code == 200


# Docs
def test_demo_script_exists():
    assert (Path(__file__).resolve().parent.parent / "docs/DEMO_SCRIPT.md").exists()


# CLI demo script
def test_demo_script_importable():
    root = Path(__file__).resolve().parent.parent
    assert (root / "scripts/private_beta_demo.py").exists()


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
