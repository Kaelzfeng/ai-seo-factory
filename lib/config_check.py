# -*- coding: utf-8 -*-
import os
from config import APP_ENV, SECRET_KEY, SQLITE_PATH, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, WP_URL, mask_secret

def load_runtime_config() -> dict:
    from config import masked_config
    return masked_config()

def validate_runtime_config(strict: bool = False) -> dict:
    warnings, errors = [], []
    if strict and "dev-secret" in SECRET_KEY:
        errors.append("SECRET_KEY must be changed from default in production")
    if not os.path.exists(os.path.dirname(SQLITE_PATH)):
        os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    return {
        "ok": len(errors) == 0,
        "environment": APP_ENV,
        "warnings": warnings,
        "errors": errors,
        "services": {
            "database": {"ok": _check_db()},
            "llm": {"configured": bool(DEEPSEEK_API_KEY or ANTHROPIC_API_KEY),
                    "provider": "deepseek" if DEEPSEEK_API_KEY else "anthropic" if ANTHROPIC_API_KEY else "mock"},
            "wordpress": {"configured": bool(WP_URL)},
            "serp": {"provider": os.getenv("SERP_PROVIDER", "mock")},
        },
    }

def _check_db() -> bool:
    try:
        from models import _get_db
        db = _get_db()
        db.execute("SELECT 1")
        return True
    except Exception:
        return False

def get_config_report(strict: bool = False) -> dict:
    v = validate_runtime_config(strict)
    v["config"] = {k: v for k, v in load_runtime_config().items()}
    return v
