# -*- coding: utf-8 -*-
"""lib/api_contract.py · Phase 8: API 合同生成"""

CATEGORIES = {
    "/login": "auth", "/register": "auth", "/logout": "auth",
    "/projects": "projects", "/api/projects": "projects",
    "/api/seo": "seo", "/api/competitor": "competitor", "/api/publish": "publish",
    "/api/health": "system", "/api/ready": "system", "/api/config": "system",
    "/api/system": "system", "/api/plans": "saas", "/api/entitlements": "saas",
    "/api/usage": "saas", "/api/billing": "saas", "/api/webhooks": "saas",
    "/api/audit": "saas", "/api/sites": "projects", "/api/generations": "seo",
    "/api/cms": "publish", "/api/keywords": "seo", "/api/batches": "seo",
    "/api/page-contents": "seo", "/api/subscription": "saas",
}

def _guess_category(rule) -> str:
    path = rule.rule
    for prefix, cat in CATEGORIES.items():
        if path.startswith(prefix):
            return cat
    return "other"

def _needs_auth(path: str) -> bool:
    public = {"/api/health", "/api/ready", "/login", "/register", "/logout", "/"}
    return path not in public

def collect_routes(app) -> list[dict]:
    routes = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.rule.startswith("/admin") or rule.rule.startswith("/static"):
            continue
        routes.append({
            "path": rule.rule,
            "methods": sorted([m for m in rule.methods if m not in ("HEAD", "OPTIONS")]),
            "auth_required": _needs_auth(rule.rule),
            "category": _guess_category(rule),
            "description": "",
        })
    return routes

def generate_api_contract(app) -> list[dict]:
    return collect_routes(app)

def write_api_contract(path: str = "docs/API.md"):
    from app import app as _app
    routes = collect_routes(_app)
    by_cat = {}
    for r in routes:
        by_cat.setdefault(r["category"], []).append(r)
    lines = ["# API Contract\n", f"Total endpoints: {len(routes)}\n"]
    for cat in ("auth", "projects", "seo", "competitor", "publish", "saas", "system"):
        if cat not in by_cat:
            continue
        lines.append(f"\n## {cat.title()}\n")
        for r in by_cat[cat]:
            auth = "🔒" if r["auth_required"] else "🌐"
            methods = ",".join(r["methods"])
            lines.append(f"- {auth} `{methods}` {r['path']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return routes

def generate_openapi_like_json(app) -> dict:
    return {"endpoints": collect_routes(app)}
