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


def apply_b2b_content_defaults(intent: dict) -> dict:
    """Complete an explicit site request without changing extraction rules.

    A product + target language + website goal is sufficient for this B2B
    product. Existing audience or market values always win.
    """
    resolved = dict(intent or {})
    has_product = bool(resolved.get("product") or resolved.get("product_phrase") or resolved.get("industry"))
    is_site_request = resolved.get("goal") == "generate website"
    if has_product and resolved.get("language") and is_site_request:
        if not resolved.get("audience") and not resolved.get("market"):
            resolved["audience"] = "B2B buyers and distributors"
    return resolved


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

    return apply_b2b_content_defaults(intent)


def intent_is_locked(intent: dict) -> bool:
    """An intent is locked when enough slots are filled to generate."""
    return is_intent_ready(intent)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "page"


def build_generation_plan(intent: dict) -> dict:
    from lib.intent_engine import get_product_for_page
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import localized_page_title

    # Phase 9.4.1: Use localized product for page content
    localized_product = get_product_for_page(intent)
    display = get_product_for_page(intent)  # same — localized for page use
    industry = str(intent.get("industry") or localized_product).strip().title()
    brief = build_industry_brief(dict(intent or {}, product=localized_product, industry=industry))
    page_types = ("supplier_guide", "manufacturer", "wholesale", "export", "specifications", "faq")
    # Use localized product in slugs
    slug_base = _slugify(f"{localized_product} {industry}")
    pages = [{
        "title": localized_page_title(brief, page_type),
        "type": page_type,
        "slug": f"{slug_base}-{page_type.replace('_', '-')}",
    } for page_type in page_types]
    plan_titles = {
        "Japanese": "サイト生成計画", "Spanish": "Plan de generación del sitio",
        "German": "Website-Erstellungsplan", "French": "Plan de génération du site",
    }
    return {"title": plan_titles.get(brief.language, "站点生成计划"), "pages": pages}


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
    from lib.intent_engine import product_display_name

    product = product_display_name(intent)
    industry = str(intent.get("industry") or product)
    language = str(intent.get("language") or "English")
    market = str(intent.get("market") or "global export markets")
    audience = str(intent.get("audience") or "B2B buyers and distributors")
    return (
        f"我理解你的需求是：为 {product} / {industry} 创建 {language} "
        f"{market} 网站，目标读者是 {audience}。"
    )


def artifact_title(intent: dict) -> str:
    from lib.intent_engine import get_product_for_page
    from lib.localization import localize_site_title
    # Phase 9.4.1: Use localized product for site title
    product = get_product_for_page(intent)
    return localize_site_title(
        product, intent.get("language"), market=intent.get("market"), site_type="B2B export"
    )


def render_fallback_artifacts(outdir, intent: dict, plan: dict) -> list[dict]:
    """Render the six planned pages when the full generator is unavailable."""
    import datetime
    from pathlib import Path
    from lib.industry_brief import build_industry_brief
    from lib.language_normalizer import normalize as normalize_language
    from lib.page_content_writer import write_page_content
    from lib.localization import localize_sentence, localize_site_title
    from lib.themes import atelier

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    brief = build_industry_brief(intent)
    locale = normalize_language(brief.language).get("locale", "en-US")
    html_lang = locale.split("-")[0].lower()
    rendered = []
    nav = [
        {"label": item["title"], "href": f"./{item['slug']}.html"}
        for item in plan.get("pages", [])
    ]
    for item in plan.get("pages", []):
        page_copy = write_page_content(item, brief)
        item["title"] = page_copy["title"]
        ctx = {
            "lang": html_lang, "org": artifact_title(intent),
            "title": page_copy["title"],
            "meta_desc": page_copy["meta_description"],
            "robots": "noindex,follow", "type_label": item["type"],
            "body_has_h1": True, "body_html": page_copy["html"], "warn_html": "",
            "jsonld": "", "year": today.year, "updated": today.isoformat(),
            "chips": [brief.industry, brief.market, "B2B", "MOQ"],
            "crumbs": [
                {"label": "Home", "href": "./index.html"},
                {"label": item["title"], "href": f"./{item['slug']}.html", "active": True},
            ],
            "nav": [dict(link, active=link["href"].endswith(f"{item['slug']}.html")) for link in nav],
        }
        html = atelier.render_page(ctx)
        (outdir / f"{item['slug']}.html").write_text(html, encoding="utf-8")
        rendered.append({
            "slug": item["slug"], "title": page_copy["title"], "type": item["type"],
            "html": html, "url": f"/output/{item['slug']}.html", "status": "done",
            "score": None, "passed": True,
        })

    site_title = localize_site_title(brief.product, brief.language, brief.market, "B2B export")
    site_sub = localize_sentence("site_sub", brief.language, {
        "product": brief.product, "market": brief.market, "buyer": brief.buyer_type,
    })
    groups = [{
        "title": site_title, "label": site_title,
        "items": [{
            "title": page["title"], "href": f"./{page['slug']}.html",
            "type": page["type"], "type_label": page["type"],
            "desc": localize_sentence("intro", brief.language, {
                "product": brief.product, "market": brief.market, "buyer": brief.buyer_type,
            }),
            "teaser": localize_sentence("intro", brief.language, {
                "product": brief.product, "market": brief.market, "buyer": brief.buyer_type,
            }), "passed": True,
        } for page in rendered],
    }]
    index_ctx = {
        "lang": html_lang, "org": site_title, "site_name": site_title,
        "sub": site_sub,
        "robots": "noindex,follow", "year": today.year,
        "stats": {"total": len(rendered), "n_pass": len(rendered), "n_skip": 0},
        "groups": groups, "nav": [{"label": "Home", "href": "./index.html", "active": True}] + nav,
    }
    (outdir / "index.html").write_text(atelier.render_index(index_ctx), encoding="utf-8")
    return rendered
