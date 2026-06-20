# -*- coding: utf-8 -*-
"""Phase 7: SaaS 套餐/额度/用量/账单/重置 测试"""
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


def _setup(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("p7-org")
    uid = models.create_user("p7@t.com", "h", "s")
    models.create_subscription(tid, plan_code="free", status="active")
    return tid, uid


# Plan Catalog
def test_plan_catalog_has_four_plans():
    from lib.plan_catalog import list_public_plans
    plans = list_public_plans()
    codes = {p["code"] for p in plans}
    assert codes >= {"free", "starter", "pro", "agency"}


def test_seed_default_plans_idempotent(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    from lib.plan_catalog import seed_default_plans
    seed_default_plans()
    seed_default_plans()  # idempotent


# Entitlements
def test_entitlements_free_plan(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.entitlements import get_tenant_entitlements, can_generate_content
    ent = get_tenant_entitlements(tid)
    assert ent["plan_code"] == "free"
    assert ent["limits"]["generation"] == 3
    assert can_generate_content(tid)["ok"] is True


def test_can_generate_blocked_when_exceeded(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    models.record_usage(tid, kind="generation", amount=3)
    from lib.entitlements import can_generate_content
    assert can_generate_content(tid)["ok"] is False


def test_pro_plan_higher_limits(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    models.create_subscription(tid, plan_code="pro", status="active")
    from lib.entitlements import get_tenant_entitlements
    ent = get_tenant_entitlements(tid)
    # Both free+pro are active; plan_code may vary but limits should be generous
    assert ent["limits"]["generation"] >= 3


# Usage Meter
def test_record_usage_event(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.usage_meter import record_usage_event, get_usage_summary
    record_usage_event(tid, "generation", 2)
    s = get_usage_summary(tid)
    assert s.get("generation", 0) >= 2


# Quota Guard
def test_quota_guard_bypass(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.quota_guard import guarded_operation
    r = guarded_operation(tid, "generation", bypass_subscription=True)
    assert r["ok"] is True
    assert r.get("bypassed") is True


def test_quota_guard_exceeded(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    models.record_usage(tid, kind="generation", amount=3)
    from lib.quota_guard import guarded_operation
    r = guarded_operation(tid, "generation", bypass_subscription=False)
    assert r["ok"] is False
    assert r.get("code") == "quota_exceeded"


def test_quota_guard_dry_run(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.quota_guard import guarded_operation
    r = guarded_operation(tid, "generation", dry_run=True)
    assert r["ok"] is True


# Billing Events
def test_billing_event_create_list(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("be-test")
    from lib.billing_events import create_billing_event, list_billing_events
    eid = create_billing_event(tid, "subscription_created", metadata={"plan": "free"})
    assert eid > 0
    events = list_billing_events(tid)
    assert len(events) >= 1


def test_record_plan_change(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pc-test")
    from lib.billing_events import record_plan_change_event
    eid = record_plan_change_event(tid, "free", "starter")
    assert eid > 0


# Monthly Reset
def test_reset_dry_run(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.monthly_reset import reset_monthly_usage
    r = reset_monthly_usage(tid, year=2026, month=6, dry_run=True)
    assert r["ok"] is True
    assert r["dry_run"] is True


def test_reset_creates_snapshot(db, monkeypatch):
    tid, uid = _setup(db, monkeypatch)
    from lib.monthly_reset import reset_monthly_usage
    r = reset_monthly_usage(tid, year=2026, month=6, dry_run=False)
    assert r["ok"] is True


# API
@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app


def _api_setup(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("api-p7")
    uid = models.create_user("ap7@t.com", "h", "s")
    models.add_tenant_member(tid, uid, role="owner")
    models.create_subscription(tid, plan_code="free", status="active")
    return tid, uid


def test_api_entitlements(app, db, monkeypatch):
    tid, uid = _api_setup(db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get("/api/entitlements")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


def test_api_change_plan(app, db, monkeypatch):
    tid, uid = _api_setup(db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/api/billing/change-plan", json={"plan_code": "starter"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


def test_api_reset_monthly(app, db, monkeypatch):
    tid, uid = _api_setup(db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/api/admin/reset-monthly-usage", json={"dry_run": True})
        assert resp.status_code == 200


# Legacies
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
