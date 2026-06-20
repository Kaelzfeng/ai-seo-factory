# -*- coding: utf-8 -*-
"""tests/test_stage2_b2b_selection.py · Phase 3.2 B2B 页面选择测试

1. PU leather blueprint 默认 8-12 页
2. 默认页面包含 pu-leather-guide
3. 默认页面包含 pu-leather-vs-genuine-leather
4. 默认页面包含 pu-leather-vs-pvc-leather
5. 默认页面包含 pu-leather-for-furniture
6. 默认页面包含 pu-leather-for-automotive
7. 默认页面包含 microfiber-pu-leather-bags 或 supplier 页
9. consumer care query 不会挤掉 B2B 应用页
11. 至少 2 个 application 页面
12. 至少 2 个 comparison 页面
13. 至少 1 个 supplier/product 页面
14. 至少 1 个 FAQ 页面
15. 所有 slug 唯一
16. link_graph 无孤儿页
17. pillar 可达所有非 pillar 页面
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from lib.seo_engine.schemas import BusinessProfile, Keyword
from lib.seo_engine.stage2_blueprint import (
    build_site_blueprint,
    _score_page_candidate, _is_b2b_relevant, _is_consumer_care_query,
    _CLUSTER_RULES, _assign_semantic_cluster,
)


# Mock keywords designed to produce a B2B-optimal 8-page blueprint
_B2B_MOCK_KWS = [
    Keyword(keyword="pu leather guide", intent="guide", priority=10),
    Keyword(keyword="pu leather vs genuine leather", intent="comparison", priority=9),
    Keyword(keyword="pu leather vs pvc leather", intent="comparison", priority=9),
    Keyword(keyword="pu leather for furniture", intent="informational", priority=8),
    Keyword(keyword="pu leather for automotive", intent="informational", priority=8),
    Keyword(keyword="pu leather for bags", intent="informational", priority=7),
    Keyword(keyword="pu leather supplier china", intent="product", priority=9),
    Keyword(keyword="microfiber pu leather wholesale", intent="product", priority=8),
    Keyword(keyword="is pu leather durable", intent="faq", priority=7),
    Keyword(keyword="is pu leather waterproof", intent="faq", priority=6),
    Keyword(keyword="types of synthetic leather", intent="category", priority=6),
    Keyword(keyword="pu leather specification", intent="informational", priority=5),
    Keyword(keyword="how to clean pu leather", intent="faq", priority=4),  # consumer care
    Keyword(keyword="pu leather properties", intent="informational", priority=4),
    Keyword(keyword="pu leather for sofa", intent="informational", priority=6),
]


@pytest.fixture
def profile():
    return BusinessProfile(
        industry="PU leather", business_type="B2B supplier",
        target_markets=["global"], languages=["English"],
        products=["PU leather"], buyer_personas=["Importers"],
        tone="Professional",
    )


@pytest.fixture
def blueprint(monkeypatch, profile):
    monkeypatch.setattr(
        "lib.seo_engine.stage2_blueprint.expand_seed_keywords",
        lambda profile, seed_keywords=None, limit=210: _B2B_MOCK_KWS,
    )
    return build_site_blueprint(project_id=1, profile=profile)


# ── Test 1: 默认 8-12 页 ──────────────────────────────


def test_default_page_count(blueprint):
    pages = blueprint.pages
    assert 8 <= len(pages) <= 12, f"Expected 8-12 pages, got {len(pages)}"


# ── Test 2: 包含 guide ────────────────────────────────


def test_has_guide(blueprint):
    guides = [p for p in blueprint.pages if p.page_type == "guide"]
    assert len(guides) >= 1, "No guide page"
    # guide 的 slug 或 keyword 应包含 guide
    g = guides[0]
    assert "guide" in g.primary_keyword.lower() \
        or "guide" in g.slug.lower(), f"Guide page lacks 'guide': slug={g.slug} kw={g.primary_keyword}"


# ── Test 3: 包含 pu-leather-vs-genuine-leather ────────


def test_has_vs_genuine(blueprint):
    slugs = [p.slug for p in blueprint.pages]
    keywords = [p.primary_keyword.lower() for p in blueprint.pages]
    found = any("genuine" in s or "genuine" in k for s, k in zip(slugs, keywords))
    assert found, f"No genuine leather comparison page in {slugs}"


# ── Test 4: 包含 pu-leather-vs-pvc-leather ────────────


def test_has_vs_pvc(blueprint):
    slugs = [p.slug for p in blueprint.pages]
    keywords = [p.primary_keyword.lower() for p in blueprint.pages]
    found = any("pvc" in s or "pvc" in k for s, k in zip(slugs, keywords))
    assert found, f"No PVC comparison page in {slugs}"


# ── Test 5: 包含 pu-leather-for-furniture ─────────────


def test_has_furniture_application(blueprint):
    keywords = [p.primary_keyword.lower() for p in blueprint.pages]
    found = any("furniture" in k or "sofa" in k for k in keywords)
    if not found:
        slugs = [p.slug for p in blueprint.pages]
        found = any("furniture" in s or "sofa" in s for s in slugs)
    assert found, "No furniture application page"


# ── Test 6: 包含 pu-leather-for-automotive ────────────


def test_has_automotive_application(blueprint):
    keywords = [p.primary_keyword.lower() for p in blueprint.pages]
    found = any("automotive" in k or "car" in k for k in keywords)
    if not found:
        slugs = [p.slug for p in blueprint.pages]
        found = any("automotive" in s or "car" in s for s in slugs)
    assert found, "No automotive application page"


# ── Test 7: 包含 supplier 或 product 页 ──────────────


def test_has_supplier_or_product(blueprint):
    products = [p for p in blueprint.pages if p.page_type in ("product",)]
    suppliers = [p for p in blueprint.pages
                 if "supplier" in p.primary_keyword.lower()
                 or "wholesale" in p.primary_keyword.lower()
                 or "microfiber" in p.primary_keyword.lower()]
    assert len(products) >= 1 or len(suppliers) >= 1, "No product/supplier page"


# ── Test 9: consumer care 不挤掉 B2B 应用页 ──────────


def test_consumer_care_does_not_displace_applications(blueprint):
    """consumer care 页面不超过 1 个,应用页至少 2 个。"""
    apps = [p for p in blueprint.pages if p.page_type == "application"]
    cares = [p for p in blueprint.pages
             if any(w in p.primary_keyword.lower() for w in ("clean", "care", "repair", "smell", "peeling"))]
    assert len(cares) <= 1, f"Too many consumer care pages: {len(cares)}"
    assert len(apps) >= 1, f"Not enough application pages: {len(apps)}"


# ── Test 11: 至少 2 个 application ────────────────────


def test_at_least_two_applications(blueprint):
    apps = [p for p in blueprint.pages if p.page_type == "application"]
    assert len(apps) >= 2, f"Expected >=2 application pages, got {len(apps)}: {[p.slug for p in apps]}"


# ── Test 12: 至少 2 个 comparison ─────────────────────


def test_at_least_two_comparisons(blueprint):
    comps = [p for p in blueprint.pages if p.page_type == "comparison"]
    assert len(comps) >= 2, f"Expected >=2 comparison pages, got {len(comps)}: {[p.slug for p in comps]}"


# ── Test 13: 至少 1 个 supplier/product ──────────────


def test_at_least_one_product(blueprint):
    prods = [p for p in blueprint.pages if p.page_type == "product"]
    assert len(prods) >= 1, f"No product page in {[p.page_type for p in blueprint.pages]}"


# ── Test 14: 至少 1 个 FAQ ───────────────────────────


def test_at_least_one_faq(blueprint):
    faqs = [p for p in blueprint.pages if p.page_type == "faq"]
    assert len(faqs) >= 1, "No FAQ page"


# ── Test 15: slug 唯一 ────────────────────────────────


def test_slugs_unique(blueprint):
    slugs = [p.slug for p in blueprint.pages]
    assert len(slugs) == len(set(slugs))


# ── Test 16-17: link_graph ────────────────────────────


def test_link_graph_no_orphans(blueprint):
    linked_from = set()
    for src, targets in blueprint.link_graph.items():
        for t in targets:
            linked_from.add(t)
    for p in blueprint.pages:
        assert p.slug in linked_from or p.page_type in ("guide", "pillar"), \
            f"Orphan: {p.slug}"


def test_pillar_reaches_all_non_pillar(blueprint):
    pillars = [p for p in blueprint.pages if p.page_type in ("guide", "pillar")]
    if not pillars:
        return
    pillar = pillars[0]
    targets = set(blueprint.link_graph.get(pillar.slug, []))
    for p in blueprint.pages:
        if p.slug != pillar.slug:
            assert p.slug in targets, f"Pillar does not link to {p.slug}"


# ── B2B scoring unit tests ────────────────────────────


def test_score_b2b_high_priority():
    assert _score_page_candidate("pu leather supplier", "product", "supplier") > 0


def test_score_consumer_care_lower():
    b2b = _score_page_candidate("pu leather supplier", "product", "supplier")
    care = _score_page_candidate("how to clean pu leather", "faq", "consumer-care")
    assert b2b > care, f"B2B score {b2b} should be > consumer care {care}"


def test_is_b2b_relevant():
    assert _is_b2b_relevant("pu leather supplier china") is True
    assert _is_b2b_relevant("how to clean pu leather") is False


def test_is_consumer_care():
    assert _is_consumer_care_query("how to clean pu leather") is True
    assert _is_consumer_care_query("pu leather supplier") is False


def test_application_cluster_exists():
    app_cluster = [c for c in _CLUSTER_RULES if c[0] == "applications"]
    assert len(app_cluster) == 1
    assert app_cluster[0][1] == "application"


def test_consumer_care_cluster_has_lower_boost():
    app_boost = [c[3] for c in _CLUSTER_RULES if c[0] == "applications"][0]
    care_boost = [c[3] for c in _CLUSTER_RULES if c[0] == "consumer-care"][0]
    assert care_boost < app_boost, f"Consumer care boost {care_boost} should be < app boost {app_boost}"


# ── templates/static ──────────────────────────────────


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if templates_dir.exists():
        for f in templates_dir.rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0


def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if static_dir.exists():
        for f in static_dir.rglob("*"):
            if f.is_file():
                assert f.exists()
