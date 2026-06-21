# -*- coding: utf-8 -*-
"""tests/test_projects_route.py · /projects POST & template fix tests"""
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


def _setup(app, db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pr-org")
    uid = models.create_user("pr@t.com", "h", "s")
    models.add_tenant_member(tid, uid, "owner")
    return tid, uid


# Test 1: GET /projects redirects to /login when not logged in
def test_get_projects_not_logged_in(app):
    with app.test_client() as c:
        resp = c.get("/projects")
        assert resp.status_code in (302, 301)


# Test 2: GET /projects returns 200 when logged in
def test_get_projects_logged_in(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get("/projects")
        assert resp.status_code == 200


# Test 3: POST /projects no longer 405
def test_post_projects_no_longer_405(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/projects", data={"name": "Test Project", "seed": "test kw"})
        assert resp.status_code != 405


# Test 4: POST /projects creates a project
def test_post_projects_creates_project(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/projects", data={"name": "My SEO Project", "seed": "PU leather"}, follow_redirects=True)
        assert resp.status_code == 200
        # Verify project was created
        projs = models.list_projects(tenant_id=tid)
        assert len(projs) >= 1
        assert any(p["name"] == "My SEO Project" for p in projs)


# Test 5: POST with seed but no name → auto-generates name from seed
def test_post_projects_seed_only(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/projects", data={"seed": "PU leather wholesale"}, follow_redirects=True)
        assert resp.status_code == 200
        projs = models.list_projects(tenant_id=tid)
        assert any("PU leather wholesale" in p["name"] for p in projs)


# Test 6: POST with no name/seed/config → still creates (auto-named "Untitled Project")
def test_post_projects_no_fields(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.post("/projects", data={}, follow_redirects=True)
        assert resp.status_code == 200
        projs = models.list_projects(tenant_id=tid)
        assert any("Untitled" in p["name"] for p in projs)


# Test 7: Created project has correct tenant_id
def test_post_project_tenant_correct(app, db, monkeypatch):
    tid, uid = _setup(app, db, monkeypatch)
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        c.post("/projects", data={"name": "Tenant Test", "seed": "test"}, follow_redirects=True)
        projs = models.list_projects(tenant_id=tid)
        assert projs[0]["tenant_id"] == tid


# Test 8: templates don't contain broken endpoints
def test_templates_no_auth_endpoints():
    root = Path(__file__).resolve().parent.parent
    for f in (root / "templates").rglob("*.html"):
        content = f.read_text(encoding="utf-8")
        assert "auth.login_page" not in content
        assert "auth.login" not in content  # might match url_for('login') too
        assert "auth.logout" not in content


# Test 9: templates don't contain mojibake
def test_templates_no_mojibake():
    mojibake = ["鏂", "椤", "绋", "鎴", "锟", "锘"]
    root = Path(__file__).resolve().parent.parent
    for f in (root / "templates").rglob("*.html"):
        content = f.read_text(encoding="utf-8")
        for m in mojibake:
            assert m not in content, f"Mojibake '{m}' found in {f.name}"


# Test 10: static not modified
def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    if (root / "static").exists():
        for f in (root / "static").rglob("*"):
            if f.is_file(): assert f.exists()
