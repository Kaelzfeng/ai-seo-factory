# -*- coding: utf-8 -*-
"""lib/surpass_strategy.py · Phase 5: 超越策略生成

从 GapMatrix + CompetitorProfile 生成 SurpassStrategy。
程序化优先 + LLM fallback。
"""

from lib.competitor_schema import (
    CompetitorProfile, GapMatrix, SurpassStrategy,
)


def build_surpass_strategy(query: str, gap_matrix: GapMatrix,
                           competitor_profiles: list[CompetitorProfile] = None,
                           business_profile=None) -> SurpassStrategy:
    """程序化生成超越策略。

    Args:
        query: 目标关键词
        gap_matrix: 缺口矩阵
        competitor_profiles: 竞品画像列表
        business_profile: 可选 BusinessProfile

    Returns:
        SurpassStrategy
    """
    rec_pages = []
    rec_sections = []
    rec_faq = []
    rec_schema = []
    rec_links = []
    diff_points = []

    for item in gap_matrix.priority_items:
        tp = item["type"]
        val = item["item"]

        if tp == "keyword":
            slug = val.lower().replace(" ", "-")[:60]
            rec_pages.append(slug)
        elif tp == "topic":
            rec_sections.append(val)
        elif tp == "schema":
            rec_schema.append(val)
        elif tp == "faq":
            rec_faq.append(val)
        elif tp == "content_depth":
            rec_sections.append("Expand to 2000+ words with detailed specifications")
        elif tp == "internal_link":
            rec_links.append("Add cross-links between related product and application pages")

    # 差异化卖点
    differentiation_points = [
        f"Exceed competitor depth: target 2500+ words with 8+ H2 sections",
        f"Add comprehensive FAQ sections with structured data",
        f"Cover B2B-specific topics competitors miss: export process, quality certifications, customization",
    ]

    # Content angle
    content_angle = f"Authoritative, data-rich {query} resource that combines buyer guide, technical specifications, and industry comparisons in one pillar page"

    # Rationale
    rationale = f"Based on analysis of {len(competitor_profiles) if competitor_profiles else 0} competitor pages. "
    rationale += f"Found {len(gap_matrix.keyword_gaps)} keyword gaps, {len(gap_matrix.schema_gaps)} schema gaps, {len(gap_matrix.faq_gaps)} FAQ gaps."

    return SurpassStrategy(
        target_keyword=query,
        recommended_pages=list(dict.fromkeys(rec_pages))[:5],  # dedup
        recommended_sections=rec_sections[:8],
        recommended_faq=rec_faq[:5],
        recommended_schema=rec_schema[:3],
        recommended_internal_links=rec_links[:3],
        content_angle=content_angle,
        differentiation_points=differentiation_points,
        priority_score=_calc_priority_score(gap_matrix),
        rationale=rationale,
    )


def _calc_priority_score(gap_matrix: GapMatrix) -> float:
    """计算优先级评分 0-100。"""
    score = 0.0
    score += min(len(gap_matrix.keyword_gaps) * 3, 30)
    score += min(len(gap_matrix.topic_gaps) * 5, 20)
    score += min(len(gap_matrix.schema_gaps) * 4, 15)
    score += min(len(gap_matrix.faq_gaps) * 3, 15)
    score += min(len(gap_matrix.content_depth_gaps) * 5, 10)
    score += min(len(gap_matrix.page_type_gaps) * 5, 10)
    return min(100, score)


def strategy_to_blueprint_hints(strategy: SurpassStrategy) -> dict:
    """Phase 5.1: 把 SurpassStrategy 转为可输入 S2 的结构化 hints dict。

    返回:
    {
        "recommended_pages": [{"slug","page_type","primary_keyword","title"}, ...],
        "recommended_sections": [...],
        "recommended_faq": [...],
        "recommended_schema": [...],
        "recommended_keywords": [...],
        "content_angle": "...",
        "differentiation_points": [...],
        "priority_score": 0-100,
    }
    """
    # 把 slug 转为结构化页面推荐
    pages = []
    for slug in strategy.recommended_pages[:8]:
        kw = slug.replace("-", " ")
        # 从 slug 推断 page_type
        pt = "article"
        if any(w in slug for w in ("vs", "compare", "difference")):
            pt = "comparison"
        elif any(w in slug for w in ("faq",)):
            pt = "faq"
        elif any(w in slug for w in ("supplier", "manufacturer", "wholesale", "product")):
            pt = "product"
        elif any(w in slug for w in ("guide", "complete")):
            pt = "guide"
        elif any(w in slug for w in ("types", "category", "applications")):
            pt = "category"
        pages.append({
            "slug": slug,
            "page_type": pt,
            "primary_keyword": kw,
            "title": kw.title(),
        })

    return {
        "recommended_pages": pages,
        "recommended_keywords": [p["primary_keyword"] for p in pages],
        "recommended_sections": strategy.recommended_sections[:8],
        "recommended_faq": strategy.recommended_faq[:5],
        "recommended_schema": strategy.recommended_schema[:3],
        "content_angle": strategy.content_angle,
        "differentiation_points": strategy.differentiation_points,
        "priority_score": strategy.priority_score,
    }


def strategy_to_markdown(strategy: SurpassStrategy) -> str:
    """把 SurpassStrategy 转为 Markdown 文本。"""
    lines = [
        f"# Surpass Strategy: {strategy.target_keyword}",
        f"**Priority Score:** {strategy.priority_score:.0f}/100",
        "",
        "## Recommended Pages",
    ]
    for p in strategy.recommended_pages:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Recommended Sections")
    for s in strategy.recommended_sections:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("## Recommended FAQ")
    for f in strategy.recommended_faq:
        lines.append(f"- {f}")
    lines.append("")
    lines.append("## Differentiation Points")
    for d in strategy.differentiation_points:
        lines.append(f"- {d}")
    lines.append("")
    lines.append(f"## Rationale\n{strategy.rationale}")
    return "\n".join(lines)
