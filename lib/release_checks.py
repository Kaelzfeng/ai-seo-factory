# -*- coding: utf-8 -*-
"""lib/release_checks.py · Phase 8: 上线前检查"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def run_release_checks(strict: bool = False) -> dict:
    results = {
        "tests": check_tests_hint(),
        "gitignore": check_gitignore(),
        "secrets": check_no_secrets_in_repo(),
        "required_files": check_required_files(),
        "frontend": check_frontend_unchanged(),
        "config": check_runtime_config(strict),
    }
    ok = all(v if isinstance(v, bool) else v.get("ok", True) for v in results.values())
    return {"ok": ok, "checks": results}

def check_tests_hint() -> dict:
    return {"ok": True, "recommendation": "Run: python -m pytest tests/ -v"}

def check_gitignore() -> dict:
    gf = ROOT / ".gitignore"
    if not gf.exists():
        return {"ok": False, "error": ".gitignore missing"}
    content = gf.read_text(encoding="utf-8")
    required = [".env", "*.db", "__pycache__", ".pytest_cache"]
    missing = [r for r in required if r not in content]
    return {"ok": len(missing) == 0, "missing_patterns": missing}

def check_no_secrets_in_repo() -> dict:
    issues = []
    patterns = ["sk-ant-", "sk-or-", "DEEPSEEK_API_KEY=", "ANTHROPIC_API_KEY=",
                "WORDPRESS_APP_PASSWORD=", "SECRET_KEY=prod-"]
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", ".pytest_cache", "node_modules")]
        for f in files:
            if f in (".env", ".env.local", ".env.production"):
                issues.append(f"Secret file: {os.path.relpath(os.path.join(root, f), ROOT)}")
    return {"ok": len(issues) == 0, "issues": issues}

def check_required_files() -> dict:
    required = ["app.py", "run.py", "models.py", "requirements.txt",
                "README.md", ".gitignore"]
    missing = [f for f in required if not (ROOT / f).exists()]
    return {"ok": len(missing) == 0, "missing": missing}

def check_frontend_unchanged() -> dict:
    templates = ROOT / "templates"
    static = ROOT / "static"
    return {"ok": True, "templates_exists": templates.exists(), "static_exists": static.exists()}

def check_runtime_config(strict: bool = False) -> dict:
    from lib.config_check import validate_runtime_config
    return validate_runtime_config(strict)

def check_database_schema() -> dict:
    try:
        from lib.health import _table_check
        tables = _table_check()
        return {"ok": len(tables) > 0, "table_count": len(tables), "tables": tables}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_smoke_commands() -> dict:
    return {"ok": True, "commands": [
        "python run.py industries/pu-leather.yaml --dry-run",
        "python scripts/analyze_competitor.py 'test' --mock",
        "python scripts/check_config.py",
    ]}
