# -*- coding: utf-8 -*-
"""lib/health.py · Phase 8: 健康检查"""
import os, sys

def health_check() -> dict:
    return {"ok": True, "status": "running", "app": "ai-seo-content-factory"}

def readiness_check() -> dict:
    db_ok = database_check()
    fs_ok = filesystem_check()
    return {
        "ok": db_ok and fs_ok,
        "database": db_ok,
        "filesystem": fs_ok,
        "tables": _table_check(),
    }

def dependency_check() -> dict:
    deps = {}
    for mod in ("flask", "yaml", "requests", "anthropic"):
        try:
            __import__(mod)
            deps[mod] = True
        except ImportError:
            deps[mod] = False
    return {"ok": all(deps.values()), "dependencies": deps}

def database_check() -> bool:
    try:
        from models import _get_db
        _get_db().execute("SELECT 1")
        return True
    except Exception:
        return False

def _table_check() -> list[str]:
    try:
        from models import _get_db
        rows = _get_db().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [r["name"] for r in rows]
    except Exception:
        return []

def filesystem_check() -> bool:
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(dir=".", delete=True) as f:
            f.write(b"test")
        return True
    except Exception:
        return False

def service_check_summary() -> dict:
    from lib.config_check import validate_runtime_config
    return validate_runtime_config(strict=False)
