# -*- coding: utf-8 -*-
"""config.py · Phase 8: 集中配置管理"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

APP_ENV = os.getenv("APP_ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", str(ROOT / "data" / "app.db"))
SQLITE_PATH = os.getenv("SQLITE_PATH", str(ROOT / "data" / "app.db"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERP_PROVIDER = os.getenv("SERP_PROVIDER", "mock")
WP_URL = os.getenv("WORDPRESS_BASE_URL", os.getenv("WP_SITE", ""))
WP_USER = os.getenv("WORDPRESS_USERNAME", os.getenv("WP_USER", ""))
WP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD", os.getenv("WP_APP_PASSWORD", ""))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
CACHE_DIR = os.getenv("CACHE_DIR", str(ROOT / ".cache"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PORT = int(os.getenv("PORT", "5000"))


def mask_secret(value: str) -> str:
    if not value: return "***"
    if len(value) <= 6: return "***"
    return value[:3] + "***" + value[-3:]


def masked_config() -> dict:
    return {
        "APP_ENV": APP_ENV,
        "SECRET_KEY": mask_secret(SECRET_KEY),
        "SQLITE_PATH": SQLITE_PATH,
        "LLM_PROVIDER": LLM_PROVIDER or "auto-detect",
        "DEEPSEEK_API_KEY": "configured" if DEEPSEEK_API_KEY else "missing",
        "ANTHROPIC_API_KEY": "configured" if ANTHROPIC_API_KEY else "missing",
        "SERP_PROVIDER": SERP_PROVIDER,
        "WP_URL": WP_URL or "not configured",
        "WP_USER": WP_USER or "not configured",
        "WP_PASSWORD": mask_secret(WP_PASSWORD) if WP_PASSWORD else "not configured",
        "WEBHOOK_URL": WEBHOOK_URL or "not configured",
        "CACHE_DIR": CACHE_DIR,
        "LOG_LEVEL": LOG_LEVEL,
        "PORT": PORT,
    }
