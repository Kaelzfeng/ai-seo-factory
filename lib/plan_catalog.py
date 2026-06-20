# -*- coding: utf-8 -*-
"""lib/plan_catalog.py · Phase 7: 套餐目录"""

_PLANS = [
    {"code": "free", "name": "Free", "monthly_generation_limit": 3, "monthly_token_limit": 100000,
     "monthly_competitor_analysis_limit": 1, "monthly_publish_sync_limit": 3,
     "max_projects": 1, "max_sites": 1, "max_batch_jobs": 0, "max_pages_per_blueprint": 8, "price_cents": 0},
    {"code": "starter", "name": "Starter", "monthly_generation_limit": 50, "monthly_token_limit": 1500000,
     "monthly_competitor_analysis_limit": 10, "monthly_publish_sync_limit": 50,
     "max_projects": 3, "max_sites": 3, "max_batch_jobs": 50, "max_pages_per_blueprint": 12, "price_cents": 19900},
    {"code": "pro", "name": "Pro", "monthly_generation_limit": 300, "monthly_token_limit": 10000000,
     "monthly_competitor_analysis_limit": 80, "monthly_publish_sync_limit": 300,
     "max_projects": 15, "max_sites": 15, "max_batch_jobs": 500, "max_pages_per_blueprint": 30, "price_cents": 69900},
    {"code": "agency", "name": "Agency", "monthly_generation_limit": 1500, "monthly_token_limit": 50000000,
     "monthly_competitor_analysis_limit": 500, "monthly_publish_sync_limit": 1500,
     "max_projects": 100, "max_sites": 100, "max_batch_jobs": 5000, "max_pages_per_blueprint": 100, "price_cents": 199900},
]


def get_plan_catalog() -> list[dict]:
    return list(_PLANS)


def get_plan_by_code(code: str) -> dict | None:
    for p in _PLANS:
        if p["code"] == code:
            return dict(p)
    return None


def list_public_plans() -> list[dict]:
    return [{k: v for k, v in p.items()} for p in _PLANS]


def validate_plan_code(code: str) -> bool:
    return get_plan_by_code(code) is not None


def seed_default_plans():
    """写入 plans 表 (幂等) + 补全缺失字段。"""
    try:
        from models import _get_db
        db = _get_db()
        for plan in _PLANS:
            db.execute(
                """INSERT OR IGNORE INTO plans (code, name, monthly_generation_limit,
                   monthly_token_limit, competitor_analysis_limit, max_projects,
                   max_sites, price_cents) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (plan["code"], plan["name"], plan["monthly_generation_limit"],
                 plan["monthly_token_limit"], plan["monthly_competitor_analysis_limit"],
                 plan["max_projects"], plan["max_sites"], plan["price_cents"]),
            )
        db.commit()
    except Exception:
        pass
