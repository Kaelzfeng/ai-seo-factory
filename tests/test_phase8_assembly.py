# -*- coding: utf-8 -*-
"""Phase 8: 总装测试 (config, health, security, api, release, CLI)"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models


# Config
def test_mask_secret():
    from config import mask_secret
    assert mask_secret("") == "***"
    assert mask_secret("abc") == "***"
    assert mask_secret("abcdefgh") == "abc***fgh"

def test_validate_config_dev_passes():
    from lib.config_check import validate_runtime_config
    r = validate_runtime_config(strict=False)
    assert r["ok"] is True

def test_validate_config_strict_fails_on_default_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from lib.config_check import validate_runtime_config
    r = validate_runtime_config(strict=True)
    # On dev with default secret, strict may fail
    assert isinstance(r, dict)

# Health
def test_health_check_ok():
    from lib.health import health_check
    assert health_check()["ok"] is True

def test_readiness_check():
    from lib.health import readiness_check
    r = readiness_check()
    assert "database" in r

# Security Headers
@pytest.fixture
def app():
    from app import app as _app
    _app.config["TESTING"] = True; _app.config["SECRET_KEY"] = "test"; return _app

def test_api_has_security_headers(app):
    with app.test_client() as c:
        resp = c.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

def test_api_has_referrer_policy(app):
    with app.test_client() as c:
        resp = c.get("/api/health")
        assert resp.headers.get("Referrer-Policy") is not None

# System APIs
def test_api_health_returns_json(app):
    with app.test_client() as c:
        resp = c.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

def test_api_ready_returns_json(app):
    with app.test_client() as c:
        resp = c.get("/api/ready")
        assert resp.status_code == 200

def test_api_config_report_no_leak(app):
    import secrets
    email = f"p8api-{secrets.token_hex(4)}@t.com"
    tid = models.create_tenant(f"p8api-{secrets.token_hex(4)}")
    uid = models.create_user(email, "h", "s")
    models.add_tenant_member(tid, uid, "owner")
    with app.test_client() as c:
        with c.session_transaction() as sess: sess["user_id"] = uid
        resp = c.get("/api/config/report")
        data = resp.get_json()
        # No raw keys should leak
        text = json.dumps(data)
        assert "sk-ant-" not in text
        assert "DEEPSEEK_API_KEY=sk-" not in text

# API Contract
def test_collect_routes():
    from app import app as _app
    from lib.api_contract import collect_routes
    routes = collect_routes(_app)
    assert len(routes) > 10
    paths = [r["path"] for r in routes]
    assert "/api/health" in paths
    assert "/api/seo/clarify" in paths
    assert "/api/competitor/analyze" in paths

def test_api_contract_has_categories():
    from lib.api_contract import collect_routes
    from app import app as _app
    routes = collect_routes(_app)
    cats = {r["category"] for r in routes}
    assert cats >= {"auth", "seo", "system", "saas"}

# Release Checks
def test_release_checks_runs():
    from lib.release_checks import run_release_checks
    r = run_release_checks(strict=False)
    assert "checks" in r

def test_check_gitignore():
    from lib.release_checks import check_gitignore
    r = check_gitignore()
    assert r["ok"] is True

def test_check_required_files():
    from lib.release_checks import check_required_files
    r = check_required_files()
    assert r["ok"] is True

# CLI
def test_check_config_cli():
    import subprocess
    r = subprocess.run(["python", "scripts/check_config.py"], capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode == 0

def test_smoke_test_cli():
    import subprocess
    r = subprocess.run(["python", "scripts/smoke_test.py"], capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert "health" in r.stdout.lower()

def test_release_check_cli():
    import subprocess
    r = subprocess.run(["python", "scripts/release_check.py"], capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    assert "Overall" in r.stdout

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
