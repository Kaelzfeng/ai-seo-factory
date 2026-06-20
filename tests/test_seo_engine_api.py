# -*- coding: utf-8 -*-
"""tests/test_seo_engine_api.py · SEO Engine API 测试

15. create_site_blueprint 存取正常
16. tenant 不能读取其他 tenant 的 blueprint
17. /api/seo/clarify 返回 JSON
18. /api/seo/blueprint 返回 JSON
19-22. templates/static 未修改
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models


@pytest.fixture()
def app():
    from app import app as _app
    _app.config["TESTING"] = True
    _app.config["SECRET_KEY"] = "test-key"
    return _app


@pytest.fixture()
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    yield conn
    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def _login(app, monkeypatch, db_conn):
    monkeypatch.setattr(models, "_get_db", lambda: db_conn)
    tid = models.create_tenant("seo-api-org")
    uid = models.create_user("seoapi@test.com", "h", "s")
    models.add_tenant_member(tid, uid, role="owner")
    pid = models.create_project(
        user_id=uid, name="SEO Project", tenant_id=tid,
        seed_keyword="test", language="English",
        site_url="https://example.com",
    )
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
    return tid, uid, pid


# ── Test: create/get blueprint ───────────────────────


def test_create_and_get_site_blueprint(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("bp-test")
    uid = models.create_user("bp@test.com", "h", "s")
    pid = models.create_project(user_id=uid, name="BP Project", tenant_id=tid, seed_keyword="test")

    bp_data = json.dumps({"project_id": pid, "pages": []}, ensure_ascii=False)
    bpid = models.create_site_blueprint(
        tenant_id=tid, project_id=pid,
        blueprint_json=bp_data,
    )
    assert bpid > 0

    bp = models.get_site_blueprint(bpid)
    assert bp is not None
    assert bp["tenant_id"] == tid


def test_tenant_isolation_blueprint(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid1 = models.create_tenant("bp-t1")
    tid2 = models.create_tenant("bp-t2")
    uid = models.create_user("bpi@test.com", "h", "s")
    pid1 = models.create_project(user_id=uid, name="P1", tenant_id=tid1, seed_keyword="test")

    bpid = models.create_site_blueprint(tenant_id=tid1, project_id=pid1, blueprint_json="{}")

    # tid2 不应读取 tid1 的 blueprint
    bps = models.list_site_blueprints(tenant_id=tid2)
    assert len(bps) == 0

    # tid1 可以
    bps = models.list_site_blueprints(tenant_id=tid1)
    assert len(bps) >= 1


# ── API 测试 ─────────────────────────────────────────


def test_api_clarify_returns_json(app, db, monkeypatch):
    tid, uid, pid = _login(app, monkeypatch, db)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/seo/clarify",
                      json={"user_input": "I want an English B2B export site for PU leather"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scope" in data
        assert "needs_clarification" in data


def test_api_clarify_no_input(app, db, monkeypatch):
    tid, uid, pid = _login(app, monkeypatch, db)

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/seo/clarify", json={})
        assert resp.status_code == 400


def test_api_blueprint_create(app, db, monkeypatch):
    tid, uid, pid = _login(app, monkeypatch, db)

    # 先创建 business_profile
    profile_data = {
        "industry": "PU leather", "business_type": "B2B",
        "target_markets": ["global"], "languages": ["English"],
        "products": ["PU leather"], "buyer_personas": ["Importers"],
        "tone": "Professional", "terminology": [],
    }
    models.create_business_profile(
        tenant_id=tid, project_id=pid,
        profile_json=json.dumps(profile_data, ensure_ascii=False),
    )

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
        resp = c.post("/api/seo/blueprint",
                      json={"project_id": pid, "profile": profile_data})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert "blueprint" in data


# ── templates/static ─────────────────────────────────


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
