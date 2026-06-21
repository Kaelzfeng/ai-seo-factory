# -*- coding: utf-8 -*-
"""Deterministic intent locking and the default six-page B2B site plan.

Phase 9.3.8: Delegates intent extraction and merge to lib.intent_engine.
"""

from __future__ import annotations

import re

from lib.intent_engine import merge_intent, is_intent_ready, build_clarification


def _contains(text: str, *terms: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def lock_intent(message: str, project: dict | None = None) -> dict:
    """Merge user message into a fresh intent and return it.

    If a project seed_keyword is available and no product was detected,
    seed it from the project as a fallback.
    """
    from lib.intent_engine import empty_intent
    intent = merge_intent(empty_intent(), message)

    # Fallback: use project seed_keyword if no product detected
    project = project or {}
    if not intent.get("product") and not intent.get("industry"):
        seed = str(project.get("seed_keyword", "")).strip()
        if seed:
            intent["product"] = seed.split()[0] if seed else ""
            intent["industry"] = seed

    return intent


def intent_is_locked(intent: dict) -> bool:
    """An intent is locked when enough slots are filled to generate."""
    return is_intent_ready(intent)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "page"


def build_generation_plan(intent: dict) -> dict:
    product = str(intent.get("product") or "product").strip().lower()
    product_title = product.title()
    industry = str(intent.get("industry") or product).strip().title()
    pages = [
        {
            "title": f"{product_title} {industry} Supplier Guide",
            "type": "supplier_guide",
        },
        {
            "title": f"{product_title} Manufacturer for Wholesale Buyers",
            "type": "manufacturer",
        },
        {
            "title": f"{product_title} Wholesale Bulk Order Guide",
            "type": "wholesale",
        },
        {
            "title": f"{product_title} Export Distributor Guide",
            "type": "export",
        },
        {
            "title": f"{product_title} Specifications Buying Guide",
            "type": "specifications",
        },
        {
            "title": f"{product_title} FAQ for B2B Buyers",
            "type": "faq",
        },
    ]
    for page in pages:
        page["slug"] = _slugify(page["title"])
    return {"title": "站点生成计划", "pages": pages}


def next_clarification(messages: list[dict]) -> str:
    """Build a contextual clarification from the intent engine.

    Uses messages to reconstruct intent state, then asks for the first
    genuinely missing slot. Falls back to a short prompt if all slots
    have been asked.
    """
    from lib.intent_engine import empty_intent, get_missing_slots

    # Reconstruct intent from the conversation history
    intent = empty_intent()
    for item in (messages or []):
        if item.get("role") == "user":
            text = str(item.get("content") or item.get("text") or "")
            if text:
                intent = merge_intent(intent, text)

    missing = get_missing_slots(intent)
    if not missing:
        return "请简短描述你的产品和目标市场，我就开始规划。"

    msg, intent = build_clarification(intent)
    return msg


def understanding_message(intent: dict) -> str:
    return (
        f"我理解你的需求是：为 {intent['product']} / {intent['industry']} "
        f"创建英文 {intent['market']} 网站，目标读者是 {intent['audience']}。"
    )


def artifact_title(intent: dict) -> str:
    return f"{str(intent.get('product') or 'Product').title()} Hardware Tools Export Site"


def render_fallback_artifacts(outdir, intent: dict, plan: dict) -> list[dict]:
    """Render the six planned pages when the full generator is unavailable."""
    import datetime
    from pathlib import Path
    from lib.themes import atelier

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    product = str(intent.get("product") or "product")
    audience = str(intent.get("audience") or "B2B buyers")
    rendered = []
    nav = [
        {"label": item["title"], "href": f"./{item['slug']}.html"}
        for item in plan.get("pages", [])
    ]
    for item in plan.get("pages", []):
        body = (
            f"<h1>{item['title']}</h1>"
            f"<p>This B2B export guide helps {audience} evaluate {product} "
            "suppliers, specifications, wholesale terms, and export readiness.</p>"
            "<h2>Supplier and Manufacturing Scope</h2>"
            f"<p>Review {product} manufacturing controls, material specifications, "
            "packaging options, lead times, and bulk order capabilities.</p>"
            "<h2>Wholesale and Export Requirements</h2>"
            "<p>Confirm commercial terms, inspection documents, shipment planning, "
            "and distributor support before ordering.</p>"
            "<blockquote>Request specifications, wholesale terms, and export documentation.</blockquote>"
        )
        ctx = {
            "lang": "en", "org": artifact_title(intent),
            "title": item["title"],
            "meta_desc": f"{item['title']} for {audience}.",
            "robots": "noindex,follow", "type_label": item["type"],
            "body_has_h1": True, "body_html": body, "warn_html": "",
            "jsonld": "", "year": today.year, "updated": today.isoformat(),
            "chips": ["B2B Export", "Wholesale", "Supplier"],
            "crumbs": [
                {"label": "Home", "href": "./index.html"},
                {"label": item["title"], "href": f"./{item['slug']}.html", "active": True},
            ],
            "nav": [dict(link, active=link["href"].endswith(f"{item['slug']}.html")) for link in nav],
        }
        html = atelier.render_page(ctx)
        (outdir / f"{item['slug']}.html").write_text(html, encoding="utf-8")
        rendered.append({
            "slug": item["slug"], "title": item["title"], "type": item["type"],
            "html": html, "url": f"/output/{item['slug']}.html", "status": "done",
            "score": None, "passed": True,
        })

    groups = [{
        "title": "B2B Export Pages", "label": "B2B Export Pages",
        "items": [{
            "title": page["title"], "href": f"./{page['slug']}.html",
            "type": page["type"], "type_label": page["type"],
            "desc": f"{page['title']} for international buyers.",
            "teaser": f"{page['title']} for international buyers.", "passed": True,
        } for page in rendered],
    }]
    index_ctx = {
        "lang": "en", "org": artifact_title(intent), "site_name": artifact_title(intent),
        "sub": f"Six-page B2B export workspace for {audience}.",
        "robots": "noindex,follow", "year": today.year,
        "stats": {"total": len(rendered), "n_pass": len(rendered), "n_skip": 0},
        "groups": groups, "nav": [{"label": "Home", "href": "./index.html", "active": True}] + nav,
    }
    (outdir / "index.html").write_text(atelier.render_index(index_ctx), encoding="utf-8")
    return rendered
