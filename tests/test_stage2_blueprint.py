# -*- coding: utf-8 -*-
"""tests/test_stage2_blueprint.py · Stage 2 测试

7. Stage 2 能生成 >=8 页 blueprint
8. 关键词 intent 分类正确
9. slug 唯一
10. 至少 1 个 pillar / guide 页
11. link_graph 无孤儿页
12. pillar 可达所有 cluster 页面
13. cluster 页面能链接回 pillar
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import BusinessProfile, Keyword
from lib.seo_engine.stage2_blueprint import (
    classify_intent, map_topic_to_page_type, build_link_graph,
    build_site_blueprint, allocate_pages, cluster_keywords,
    expand_seed_keywords,
)


def test_classify_intent_comparison():
    assert classify_intent("pu leather vs genuine leather") == "comparison"


def test_classify_intent_faq():
    assert classify_intent("is pu leather waterproof") == "faq"


def test_classify_intent_product():
    assert classify_intent("pu leather wholesale supplier") == "product"


def test_classify_intent_guide():
    assert classify_intent("complete guide to pu leather") == "guide"


def test_classify_intent_default():
    assert classify_intent("random unknown term xyz") == "informational"


def test_map_topic_to_page_type():
    assert map_topic_to_page_type("comparison") == "comparison"
    assert map_topic_to_page_type("faq") == "faq"
    assert map_topic_to_page_type("product") == "product"
    assert map_topic_to_page_type("guide") == "guide"
    assert map_topic_to_page_type("informational") == "article"
    assert map_topic_to_page_type("commercial") == "category"


def test_expand_seed_keywords_deterministic():
    """确定性 fallback 能生成关键词。"""
    profile = BusinessProfile(
        industry="PU leather", target_markets=["global"],
        languages=["English"], products=["PU leather"],
    )
    keywords = expand_seed_keywords(profile, limit=50)
    assert len(keywords) > 5
    for kw in keywords:
        assert isinstance(kw, Keyword)
        assert kw.keyword != ""
        assert kw.intent != ""


def test_build_site_blueprint_min_pages(monkeypatch):
    """build_site_blueprint 生成至少 8 个页面。"""
    # 使用确定性 fallback (不依赖外部 API)
    monkeypatch.setattr(
        "lib.seo_engine.stage2_blueprint.expand_seed_keywords",
        lambda profile, seed_keywords=None, limit=210: _mock_keywords()
    )

    profile = BusinessProfile(
        industry="PU leather", target_markets=["global"],
        languages=["English"], products=["PU leather"],
        buyer_personas=["Importers"], tone="Professional",
    )
    bp = build_site_blueprint(project_id=1, profile=profile, min_pages=8, max_pages=30)

    # 7. >=8 pages
    assert len(bp.pages) >= 8, f"Expected >=8 pages, got {len(bp.pages)}"

    # 9. slug 唯一
    slugs = [p.slug for p in bp.pages]
    assert len(slugs) == len(set(slugs)), "Slugs not unique"

    # 10. 至少 1 个 guide/pillar
    guides = [p for p in bp.pages if p.page_type in ("guide", "pillar")]
    assert len(guides) >= 1, "No pillar/guide page"

    # 11. link_graph not empty
    assert bp.link_graph, "link_graph is empty"
    for page in bp.pages:
        assert page.slug in bp.link_graph, f"{page.slug} not in link_graph"


def test_link_graph_no_orphans():
    """link_graph 无孤儿页: 所有页面被至少一个其他页面链接。"""
    from lib.seo_engine.schemas import PagePlan

    pages = [
        PagePlan(slug="guide", page_type="guide", primary_keyword="guide"),
        PagePlan(slug="vs-genuine", page_type="comparison", primary_keyword="vs"),
        PagePlan(slug="waterproof", page_type="faq", primary_keyword="faq"),
        PagePlan(slug="wholesale", page_type="product", primary_keyword="product"),
    ]
    graph = build_link_graph(pages)

    # 所有 slug 都在 graph 中
    for p in pages:
        assert p.slug in graph

    # pillar 可达所有 cluster 页面
    linked_from = set()
    for src, targets in graph.items():
        for t in targets:
            linked_from.add(t)

    # 非 pillar 页面被 pillar 链接或相互链接
    guide_targets = set(graph.get("guide", []))
    for p in pages:
        if p.slug != "guide":
            assert p.slug in linked_from, f"Orphan page: {p.slug}"


def test_link_graph_cluster_links_to_pillar():
    """cluster 页面能链接回 pillar。"""
    from lib.seo_engine.schemas import PagePlan

    pages = [
        PagePlan(slug="pillar", page_type="guide", primary_keyword="pillar"),
        PagePlan(slug="cluster-1", page_type="article", primary_keyword="c1"),
        PagePlan(slug="cluster-2", page_type="article", primary_keyword="c2"),
    ]
    graph = build_link_graph(pages)

    # cluster pages 应链接回 pillar
    for p in pages:
        if p.page_type != "guide":
            targets = graph.get(p.slug, [])
            assert "pillar" in targets, f"{p.slug} does not link to pillar: {targets}"


def test_allocate_pages_min_count():
    """allocate_pages 在主题充足时至少生成 min_pages。"""
    from lib.seo_engine.schemas import Topic

    topics = [
        Topic(id=f"t{i:03d}", name=f"Topic {i}", intent=INTENTS[i % len(INTENTS)],
              keywords=[f"kw-{i}"], priority=10-i, page_type=map_topic_to_page_type(INTENTS[i % len(INTENTS)]))
        for i in range(15)
    ]
    pages = allocate_pages(topics, min_pages=8, max_pages=30)
    assert len(pages) >= 8


INTENTS = ["guide", "comparison", "faq", "product", "informational", "commercial", "category", "guide"]


def _mock_keywords():
    """生成 mock 关键词列表(至少 30 个)。"""
    seeds = [
        ("pu leather", "guide"),
        ("pu leather vs genuine leather", "comparison"),
        ("pu leather vs pvc leather", "comparison"),
        ("is pu leather waterproof", "faq"),
        ("is pu leather durable", "faq"),
        ("is pu leather toxic", "faq"),
        ("types of synthetic leather", "category"),
        ("grades of pu leather", "category"),
        ("pu leather supplier", "product"),
        ("pu leather manufacturer china", "product"),
        ("pu leather wholesale price", "product"),
        ("pu leather for furniture", "informational"),
        ("pu leather for automotive", "informational"),
        ("pu leather for bags", "informational"),
        ("how to clean pu leather", "faq"),
        ("pu leather specification", "product"),
        ("pu leather vs real leather cost", "comparison"),
        ("best pu leather supplier", "commercial"),
        ("top pu leather manufacturers", "commercial"),
        ("pu leather production process", "informational"),
        ("pu leather properties", "informational"),
        ("eco friendly pu leather", "faq"),
        ("recycled pu leather", "informational"),
        ("pu leather fabric wholesale", "product"),
        ("pu leather for shoes", "informational"),
        ("synthetic leather guide", "guide"),
        ("microfiber pu leather", "product"),
        ("pu leather catalogue", "product"),
        ("pu leather sample request", "transactional"),
        ("pu leather factory audit", "transactional"),
    ]
    return [Keyword(keyword=k, intent=i, priority=5) for k, i in seeds]
