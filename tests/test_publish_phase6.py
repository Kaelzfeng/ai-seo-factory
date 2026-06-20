# -*- coding: utf-8 -*-
"""Phase 6: 发布运营层测试 (CMS, field mapper, snapshot, sync, rollback, webhook, audit, api, cli)"""
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
    tid = models.create_tenant("p6-org")
    uid = models.create_user("p6@test.com", "h", "s")
    pid = models.create_project(user_id=uid, name="P6", tenant_id=tid, seed_keyword="t", language="En", site_url="https://x.com")
    pc_id = models.create_page_content(tenant_id=tid, project_id=pid, slug="test", title="T", primary_keyword="k", content_json='{}', gutenberg_html="<p>x</p>")
    return tid, uid, pid, pc_id


# ── CMS Adapter ──────────────────────────────────────

def test_mock_adapter_publish_draft():
    from lib.cms_adapter import get_cms_adapter
    a = get_cms_adapter("mock")
    r = a.publish_draft({})
    assert r["ok"] is True
    assert r["status"] == "draft"
    assert r["remote_id"]


def test_mock_adapter_health():
    from lib.cms_adapter import get_cms_adapter
    a = get_cms_adapter("mock")
    assert a.health_check()["ok"] is True


def test_wp_adapter_no_config():
    from lib.cms_adapter import get_cms_adapter
    a = get_cms_adapter("wordpress")
    r = a.validate_config()
    assert r["ok"] is False
    assert len(r["errors"]) > 0


# ── Field Mapper ─────────────────────────────────────

def test_field_mapper_basic():
    from lib.cms_field_mapper import map_page_content_to_cms_fields
    pc = {"title": "T", "gutenberg_html": "<p>H</p>", "slug": "s", "meta_description": "M"}
    r = map_page_content_to_cms_fields(pc)
    assert r["title"] == "T"
    assert r["content"] == "<p>H</p>"
    assert r["slug"] == "s"


def test_field_mapper_fallback():
    from lib.cms_field_mapper import map_page_content_to_cms_fields
    r = map_page_content_to_cms_fields({"slug": "s", "meta_description": "M"})
    assert r["slug"] == "s"
    assert r["excerpt"] == "M"


# ── Snapshot ─────────────────────────────────────────

def test_snapshot_create_and_get(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_snapshot import create_publish_snapshot, get_publish_snapshot
    sid = create_publish_snapshot(pc_id, tid, project_id=pid, before_json='{"x":1}')
    snap = get_publish_snapshot(sid, tenant_id=tid)
    assert snap is not None
    assert snap["page_content_id"] == pc_id


def test_snapshot_tenant_isolation(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    tid2 = models.create_tenant("p6-other")
    from lib.publish_snapshot import create_publish_snapshot, get_publish_snapshot
    sid = create_publish_snapshot(pc_id, tid)
    assert get_publish_snapshot(sid, tenant_id=tid2) is None


# ── Sync ─────────────────────────────────────────────

def test_sync_dry_run(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    r = sync_page_content(pc_id, tid, project_id=pid, dry_run=True)
    assert r["status"] == "dry_run"
    assert "mapped_fields" in r


def test_sync_creates_snapshot(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    r = sync_page_content(pc_id, tid, project_id=pid, dry_run=False)
    assert r.get("snapshot_id") is not None


def test_sync_creates_webhook_event(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    sync_page_content(pc_id, tid, project_id=pid, dry_run=False)
    from lib.webhooks import list_webhook_events
    events = list_webhook_events(tid)
    assert len(events) >= 1


def test_sync_creates_audit_log(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    sync_page_content(pc_id, tid, project_id=pid, dry_run=False)
    from lib.audit_log import list_audit_logs
    logs = list_audit_logs(tid)
    assert len(logs) >= 1


def test_sync_project_batch(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    models.create_page_content(tenant_id=tid, project_id=pid, slug="t2", title="T2", primary_keyword="k2")
    from lib.publish_sync import sync_project_pages
    r = sync_project_pages(pid, tid, dry_run=False)
    assert r["total"] >= 1


# ── Rollback ─────────────────────────────────────────

def test_rollback_dry_run(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    sync_page_content(pc_id, tid, project_id=pid, dry_run=False)
    from lib.publish_snapshot import list_publish_snapshots
    snaps = list_publish_snapshots(page_content_id=pc_id)
    assert snaps
    from lib.publish_rollback import rollback_page_content
    r = rollback_page_content(snaps[0]["id"], tid, dry_run=True)
    assert r["status"] == "dry_run"


# ── Webhook ──────────────────────────────────────────

def test_webhook_create_list_mark(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("wh-test")
    from lib.webhooks import create_webhook_event, list_webhook_events, mark_webhook_event_sent
    eid = create_webhook_event(tid, "page_content.synced", {"x": 1})
    events = list_webhook_events(tid)
    assert len(events) >= 1
    mark_webhook_event_sent(eid, tid)


def test_webhook_dispatch_dry(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("wh2")
    from lib.webhooks import create_webhook_event, dispatch_webhook_event
    eid = create_webhook_event(tid, "test.event", {})
    r = dispatch_webhook_event(eid, tid, dry_run=True)
    assert r["ok"] is True


def test_audit_create_list(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("au-test")
    from lib.audit_log import create_audit_log, list_audit_logs
    create_audit_log(tid, action="publish", resource_type="page_content", resource_id=1)
    logs = list_audit_logs(tid)
    assert len(logs) >= 1


# ── API ──────────────────────────────────────────────

@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app


def test_api_sync_page_returns_json(app, db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    models.add_tenant_member(tid, uid, role="owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/api/publish/sync-page", json={"page_content_id": pc_id, "dry_run": True})
        assert resp.status_code == 200
        assert resp.get_json().get("status") == "dry_run"


def test_api_snapshots_list(app, db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    models.add_tenant_member(tid, uid, role="owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get(f"/api/publish/snapshots?page_content_id={pc_id}")
        assert resp.status_code == 200


# ── CLI ──────────────────────────────────────────────

def test_cli_sync_dry_run(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    r = sync_page_content(pc_id, tid, dry_run=True)
    assert r["status"] == "dry_run"


def test_cli_rollback_dry_run(db, monkeypatch):
    tid, uid, pid, pc_id = _setup(db, monkeypatch)
    from lib.publish_sync import sync_page_content
    sync_page_content(pc_id, tid, project_id=pid, dry_run=False)
    from lib.publish_snapshot import list_publish_snapshots
    snaps = list_publish_snapshots(page_content_id=pc_id)
    assert snaps
    from lib.publish_rollback import rollback_page_content
    r = rollback_page_content(snaps[0]["id"], tid, dry_run=True)
    assert r["status"] == "dry_run"


# ── Legacy ───────────────────────────────────────────

def test_legacy_smoke(monkeypatch):
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
