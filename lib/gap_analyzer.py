# -*- coding: utf-8 -*-
"""lib/gap_analyzer.py · Phase 5: 内容缺口分析

对比竞品 profile 和自有 blueprint, 生成 GapMatrix。
"""

from collections import Counter
from lib.competitor_schema import CompetitorProfile, GapMatrix


# 所有权重
_GAP_WEIGHTS = {
    "keyword": 5, "topic": 4, "schema": 3, "faq": 3,
    "content_depth": 2, "internal_link": 2, "page_type": 4,
}


def compare_against_blueprint(competitor_profiles: list[CompetitorProfile],
                              site_blueprint=None,
                              business_profile=None) -> GapMatrix:
    """对比竞品和自有 blueprint。"""
    return build_gap_matrix(competitor_profiles, own_pages=None, site_blueprint=site_blueprint)


def build_gap_matrix(competitor_profiles: list[CompetitorProfile],
                     own_pages: list = None,
                     site_blueprint=None) -> GapMatrix:
    """构建缺口矩阵。"""
    # 聚合竞品数据
    all_keywords = Counter()
    all_schema_types = Counter()
    all_page_types = Counter()
    faq_questions = set()
    max_depth = 0
    max_internal_links = 0

    for cp in competitor_profiles:
        for kw in cp.keywords:
            all_keywords[kw] += 1
        for st in cp.schema_types:
            all_schema_types[st] += 1
        all_page_types["article"] += 1  # default
        for fi in cp.faq_items:
            q = fi.get("question", "")
            if q:
                faq_questions.add(q)
        max_depth = max(max_depth, cp.content_depth_score)
        if cp.raw_signals:
            max_internal_links = max(max_internal_links, cp.raw_signals.internal_links_count)

    # 关键词缺口: 竞品有而我们可能没有的
    keyword_gaps = [kw for kw, cnt in all_keywords.most_common(15) if cnt >= 2]

    # 主题缺口
    topic_gaps = [
        f"Detailed {kw} comparison" for kw in list(all_keywords.keys())[:5]
    ]

    # Schema 缺口
    schema_gaps = [f"Add {st} schema" for st in all_schema_types.keys()]

    # FAQ 缺口
    faq_gaps = [f"Add FAQ: {q}" for q in list(faq_questions)[:8]]

    # 内容深度缺口
    content_depth_gaps = []
    if max_depth < 50:
        content_depth_gaps.append("Content depth below average — target 2000+ words with 5+ H2 sections")

    # 内链缺口
    internal_link_gaps = []
    if max_internal_links < 8:
        internal_link_gaps.append("Few internal links — target 10+ per page")

    # 页面类型缺口
    page_type_gaps = []
    required_types = {"guide", "comparison", "faq", "product", "application"}
    existing = set(all_page_types.keys())
    for pt in required_types - existing:
        page_type_gaps.append(f"Missing page type: {pt}")

    # 优先级排序
    priority_items = _prioritize(keyword_gaps, topic_gaps, schema_gaps,
                                 faq_gaps, content_depth_gaps,
                                 internal_link_gaps, page_type_gaps)

    return GapMatrix(
        keyword_gaps=keyword_gaps,
        topic_gaps=topic_gaps,
        schema_gaps=schema_gaps,
        faq_gaps=faq_gaps,
        content_depth_gaps=content_depth_gaps,
        internal_link_gaps=internal_link_gaps,
        page_type_gaps=page_type_gaps,
        priority_items=priority_items,
    )


def _prioritize(keyword_gaps, topic_gaps, schema_gaps,
                faq_gaps, content_depth_gaps,
                internal_link_gaps, page_type_gaps) -> list[dict]:
    """按权重排序缺口。"""
    items = []
    for kw in keyword_gaps[:5]:
        items.append({"type": "keyword", "item": kw, "priority": _GAP_WEIGHTS["keyword"]})
    for tp in topic_gaps[:3]:
        items.append({"type": "topic", "item": tp, "priority": _GAP_WEIGHTS["topic"]})
    for st in schema_gaps[:3]:
        items.append({"type": "schema", "item": st, "priority": _GAP_WEIGHTS["schema"]})
    for fq in faq_gaps[:3]:
        items.append({"type": "faq", "item": fq, "priority": _GAP_WEIGHTS["faq"]})
    for cd in content_depth_gaps:
        items.append({"type": "content_depth", "item": cd, "priority": _GAP_WEIGHTS["content_depth"]})
    items.sort(key=lambda x: x["priority"], reverse=True)
    return items


def prioritize_gaps(gap_matrix: GapMatrix) -> list[dict]:
    """重新排序 GapMatrix.priority_items。"""
    return sorted(gap_matrix.priority_items, key=lambda x: x["priority"], reverse=True)
