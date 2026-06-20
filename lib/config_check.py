# -*- coding: utf-8 -*-
import os
from config import APP_ENV, SECRET_KEY, SQLITE_PATH, LLM_PROVIDER, LLM_MODEL
from config import DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, WP_URL

def load_runtime_config() -> dict:
    from config import masked_config
    return masked_config()

def _resolve_llm_provider() -> str:
    p = LLM_PROVIDER.strip().lower()
    if p:
        return p
    if DEEPSEEK_API_KEY:
        return "deepseek"
    if OPENAI_API_KEY:
        return "openai"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return "mock"  # no keys at all → mock

def _has_llm_key(provider: str) -> bool:
    keys = {"deepseek": DEEPSEEK_API_KEY, "openai": OPENAI_API_KEY,
            "anthropic": ANTHROPIC_API_KEY, "mock": True}
    return bool(keys.get(provider))

def validate_runtime_config(strict: bool = False) -> dict:
    warnings, errors = [], []
    provider = _resolve_llm_provider()

    if strict and "dev-secret" in SECRET_KEY:
        errors.append("SECRET_KEY must be changed from default in production")

    # LLM config validation
    if strict and provider != "mock" and not _has_llm_key(provider):
        errors.append(f"LLM_PROVIDER={provider} but no API key configured")

    if not os.path.exists(os.path.dirname(SQLITE_PATH)):
        os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)

    return {
        "ok": len(errors) == 0,
        "environment": APP_ENV,
        "warnings": warnings,
        "errors": errors,
        "services": {
            "database": {"ok": _check_db()},
            "llm": {
                "configured": _has_llm_key(provider),
                "provider": provider,
                "model": LLM_MODEL or "(default)",
                "api_key_present": _has_llm_key(provider),
            },
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
