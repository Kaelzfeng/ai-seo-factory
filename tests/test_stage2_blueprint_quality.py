# -*- coding: utf-8 -*-
"""tests/test_stage2_blueprint_quality.py · Phase 3.1 Blueprint 质量测试

1. build_site_blueprint 默认生成 8-12 页
2. 所有 slug 唯一
3. slug 不包含 other-topics
4. title 不包含 other-topics
5. title 不为空
6. primary_keyword 不为空
7. 至少 1 个 pillar / guide
8. pillar primary_keyword 不能是过窄应用词
9. 至少包含 comparison 页面
10. 至少包含 FAQ 页面
11. 至少包含 product/category/application 页面
12. link_graph 无孤儿页
13. pillar 可达所有非 pillar 页面
14. 所有非 pillar 页面能链接回 pillar
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from lib.seo_engine.schemas import BusinessProfile
from lib.seo_engine.stage2_blueprint import (
    build_site_blueprint, _generate_title, _make_slug, classify_intent,
    _assign_semantic_cluster, Keyword,
)


_MOCK_KWS = [
    Keyword(keyword="pu leather guide", intent="guide", priority=10),
    Keyword(keyword="pu leather vs genuine leather", intent="comparison", priority=9),
    Keyword(keyword="pu leather vs pvc leather", intent="comparison", priority=8),
    Keyword(keyword="is pu leather waterproof", intent="faq", priority=7),
    Keyword(keyword="is pu leather durable", intent="faq", priority=6),
    Keyword(keyword="pu leather for furniture", intent="informational", priority=8),
    Keyword(keyword="pu leather for automotive", intent="informational", priority=7),
    Keyword(keyword="pu leather supplier", intent="product", priority=9),
    Keyword(keyword="microfiber pu leather wholesale", intent="product", priority=8),
    Keyword(keyword="pu leather factory price", intent="product", priority=7),
    Keyword(keyword="types of synthetic leather", intent="category", priority=5),
    Keyword(keyword="pu leather specification", intent="informational", priority=4),
    Keyword(keyword="how to clean pu leather", intent="faq", priority=5),
    Keyword(keyword="pu leather properties", intent="informational", priority=3),
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
    # 使用 mock keywords 避免真实 API 调用
    monkeypatch.setattr(
        "lib.seo_engine.stage2_blueprint.expand_seed_keywords",
        lambda profile, seed_keywords=None, limit=210: _MOCK_KWS,
    )
    return build_site_blueprint(project_id=1, profile=profile)


# ── Test 1: 默认 8-12 页 ──────────────────────────────


def test_default_page_count_8_to_12(blueprint):
    pages = blueprint.pages
    assert 8 <= len(pages) <= 12, f"Expected 8-12 pages, got {len(pages)}"


# ── Test 2: slug 唯一 ─────────────────────────────────


def test_all_slugs_unique(blueprint):
    slugs = [p.slug for p in blueprint.pages]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"


# ── Test 3: slug 不包含 other-topics ──────────────────


def test_no_other_topics_in_slugs(blueprint):
    for p in blueprint.pages:
        assert "other-topics" not in p.slug, f"Bad slug: {p.slug}"
        assert "other" not in p.slug.lower(), f"'other' in slug: {p.slug}"


# ── Test 4: title 不包含 other-topics ─────────────────


def test_no_other_topics_in_titles(blueprint):
    for p in blueprint.pages:
        assert "other-topics" not in p.title.lower(), f"Bad title: {p.title}"
        assert "other" not in p.title.lower(), f"'other' in title: {p.title}"


# ── Test 5: title 不为空 ──────────────────────────────


def test_all_titles_nonempty(blueprint):
    for p in blueprint.pages:
        assert p.title and p.title.strip(), f"Empty title for {p.slug}"


# ── Test 6: primary_keyword 不为空 ────────────────────


def test_all_primary_keywords_nonempty(blueprint):
    for p in blueprint.pages:
        assert p.primary_keyword and p.primary_keyword.strip(), f"Empty pk for {p.slug}"


# ── Test 7: 至少 1 个 pillar/guide ────────────────────


def test_at_least_one_guide(blueprint):
    guides = [p for p in blueprint.pages if p.page_type in ("guide", "pillar")]
    assert len(guides) >= 1, "No guide/pillar page"


# ── Test 8: pillar primary_keyword 不能是过窄应用词 ───


def test_pillar_not_narrow_application(blueprint):
    narrow = {"for sofa", "for chair", "for bag", "for shoe"}
    for p in blueprint.pages:
        if p.page_type in ("guide", "pillar"):
            pk_lower = p.primary_keyword.lower()
            assert not any(n in pk_lower for n in narrow), f"Pillar has narrow kw: {p.primary_keyword}"


# ── Test 9: 至少包含 comparison 页面 ──────────────────


def test_at_least_one_comparison(blueprint):
    comps = [p for p in blueprint.pages if p.page_type == "comparison"]
    assert len(comps) >= 1, "No comparison page"


# ── Test 10: 至少包含 FAQ 页面 ────────────────────────


def test_at_least_one_faq(blueprint):
    faqs = [p for p in blueprint.pages if p.page_type == "faq"]
    assert len(faqs) >= 1, "No FAQ page"


# ── Test 11: 至少包含 product/category/application ────


def test_at_least_one_product_or_category(blueprint):
    types = {p.page_type for p in blueprint.pages}
    assert bool({"product", "category", "article"} & types), f"No product/category/article in {types}"


# ── Test 12: link_graph 无孤儿页 ──────────────────────


def test_link_graph_no_orphans(blueprint):
    linked_from = set()
    for src, targets in blueprint.link_graph.items():
        for t in targets:
            linked_from.add(t)
    for p in blueprint.pages:
        assert p.slug in linked_from or p.page_type in ("guide", "pillar"), \
            f"Orphan page: {p.slug} (not linked from any other page)"


# ── Test 13: pillar 可达所有非 pillar 页面 ────────────


def test_pillar_reaches_all(blueprint):
    pillars = [p.slug for p in blueprint.pages if p.page_type in ("guide", "pillar")]
    if not pillars:
        return
    pillar = pillars[0]
    targets = set(blueprint.link_graph.get(pillar, []))
    non_pillars = [p.slug for p in blueprint.pages if p.slug != pillar]
    for np_slug in non_pillars:
        assert np_slug in targets, f"Pillar {pillar} does not link to {np_slug}"


# ── Test 14: 非 pillar 页面链接回 pillar ──────────────


def test_all_link_back_to_pillar(blueprint):
    pillars = [p.slug for p in blueprint.pages if p.page_type in ("guide", "pillar")]
    if not pillars:
        return
    pillar = pillars[0]
    for p in blueprint.pages:
        if p.slug != pillar:
            links = blueprint.link_graph.get(p.slug, [])
            assert pillar in links, f"{p.slug} does not link back to pillar {pillar}: {links}"


# ── Title generation tests ────────────────────────────


def test_generate_guide_title():
    t = _generate_title("pu leather guide", "guide", "B2B Buyers")
    assert "PU Leather" in t or "pu leather" in t.lower()
    assert t.strip() != ""
    assert t != "pu-leather-guide"


def test_generate_comparison_title():
    t = _generate_title("pu leather vs genuine leather", "comparison")
    assert "PU Leather" in t or "pu leather" in t.lower()
    assert "Vs" in t or "vs" in t.lower() or "Differences" in t


def test_generate_faq_title():
    t = _generate_title("is pu leather waterproof", "faq")
    assert t.strip() != ""


def test_make_slug_from_keyword():
    assert _make_slug("pu leather for sofa") == "pu-leather-for-sofa"
    assert _make_slug("is pu leather safe") == "is-pu-leather-safe"
    assert _make_slug("PU Leather Supplier") == "pu-leather-supplier"


# ── Semantic cluster tests ────────────────────────────


def test_semantic_cluster_comparison():
    kw = Keyword(keyword="pu leather vs genuine leather", intent="comparison")
    c = _assign_semantic_cluster(kw)
    assert c == "comparison"


def test_semantic_cluster_applications():
    kw = Keyword(keyword="pu leather for furniture", intent="informational")
    c = _assign_semantic_cluster(kw)
    assert c == "applications"


def test_semantic_cluster_supplier():
    kw = Keyword(keyword="pu leather supplier china", intent="product")
    c = _assign_semantic_cluster(kw)
    assert c == "supplier-commercial"


def test_semantic_cluster_durability():
    kw = Keyword(keyword="is pu leather durable", intent="faq")
    c = _assign_semantic_cluster(kw)
    assert c == "durability-safety"


def test_semantic_cluster_guide():
    kw = Keyword(keyword="complete guide to pu leather", intent="guide")
    c = _assign_semantic_cluster(kw)
    assert c == "guide-basics"
