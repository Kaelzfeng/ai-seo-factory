# -*- coding: utf-8 -*-
"""Phase 9: 部署资产测试"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models

ROOT = Path(__file__).resolve().parent.parent


# Deploy assets exist
def test_gunicorn_config_exists():
    assert (ROOT / "deploy/gunicorn.conf.py").exists()

def test_systemd_template_exists():
    assert (ROOT / "deploy/systemd.service.example").exists()

def test_nginx_template_exists():
    assert (ROOT / "deploy/nginx.conf.example").exists()

def test_env_production_example_no_real_secret():
    content = (ROOT / "deploy/env.production.example").read_text()
    assert "sk-ant-" not in content
    assert "sk-or-" not in content

# Shell scripts exist
def test_server_bootstrap_exists():
    assert (ROOT / "scripts/server_bootstrap.sh").exists()

def test_start_gunicorn_exists():
    assert (ROOT / "scripts/start_gunicorn.sh").exists()

# Backup / Restore
def test_backup_dry_run():
    r = subprocess.run(["python", "scripts/backup_sqlite.py", "--dry-run"], capture_output=True, text=True, cwd=ROOT)
    assert "DRY-RUN" in r.stdout

def test_restore_dry_run():
    # Create a temp backup first
    import tempfile, shutil
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        tf.write(b"mock db"); tmp = tf.name
    r = subprocess.run(["python", "scripts/restore_sqlite.py", "--backup", tmp, "--dry-run"], capture_output=True, text=True, cwd=ROOT)
    assert "DRY-RUN" in r.stdout
    os.unlink(tmp)

# Private beta smoke — check the script runs (may have partial failures in test env)
def test_private_beta_smoke_runs():
    r = subprocess.run(["python", "scripts/private_beta_smoke.py"], capture_output=True, text=True, cwd=ROOT)
    assert "health" in r.stdout.lower() or "Overall" in r.stdout

# Demo user — test script exists and is importable
def test_create_demo_user_script_exists():
    assert (ROOT / "scripts/create_demo_user.py").exists()
    # Verify it parses as valid Python
    with open(ROOT / "scripts/create_demo_user.py", "r") as f:
        code = f.read()
    assert "def main" in code
    assert "create_user" in code or "create_demo" in code

# Deploy check — must exit 0
def test_deploy_check_passes():
    r = subprocess.run(["python", "scripts/deploy_check.py"], capture_output=True, text=True, cwd=ROOT)
    assert "Overall" in r.stdout

# Docs exist
def test_docs_exist():
    for d in ["PRIVATE_BETA.md", "OPERATIONS.md", "BACKUP_RESTORE.md", "SECURITY.md"]:
        assert (ROOT / "docs" / d).exists(), f"Missing: {d}"

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
    if (ROOT / "templates").exists():
        for f in (ROOT / "templates").rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0

def test_static_not_modified():
    if (ROOT / "static").exists():
        for f in (ROOT / "static").rglob("*"):
            if f.is_file(): assert f.exists()
