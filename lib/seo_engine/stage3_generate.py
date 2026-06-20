# -*- coding: utf-8 -*-
"""lib/seo_engine/stage3_generate.py · Stage 3: PagePlan → PageContent

逐页 LLM 生成,复用 run.py 的 4-tier retry + 内容验证。
"""

import datetime
import time

from lib.seo_engine.schemas import PageContent, PagePlan, BusinessProfile, SiteBlueprint


def page_plan_to_prompt_context(page_plan: PagePlan,
                                business_profile: BusinessProfile = None,
                                blueprint: SiteBlueprint = None) -> str:
    """把 PagePlan + BusinessProfile 转为 LLM prompt 上下文字符串。"""
    bp = business_profile
    pp = page_plan

    lines = [
        f"PAGE TYPE: {pp.page_type}",
        f"PRIMARY KEYWORD: {pp.primary_keyword}",
    ]
    if pp.secondary_keywords:
        lines.append(f"SECONDARY KEYWORDS: {', '.join(pp.secondary_keywords)}")
    if pp.suggested_sections:
        lines.append(f"SUGGESTED SECTIONS: {', '.join(pp.suggested_sections)}")
    if pp.internal_links:
        lines.append(f"INTERNAL LINKS TO INCLUDE: {', '.join(pp.internal_links)}")

    if bp:
        lines.extend([
            f"INDUSTRY: {bp.industry}",
            f"BUSINESS TYPE: {bp.business_type}",
            f"TARGET MARKETS: {', '.join(bp.target_markets)}",
            f"LANGUAGES: {', '.join(bp.languages)}",
            f"PRODUCTS: {', '.join(bp.products)}",
            f"TONE: {bp.tone}",
        ])
        if bp.terminology:
            lines.append(f"TERMINOLOGY: {', '.join(bp.terminology[:10])}")

    # Phase 5.1: Inject competitor gap hints
    gap_hints = getattr(pp, 'competitor_gap_hints', []) or []
    rec_faq = getattr(pp, 'recommended_faq', []) or []
    rec_schema = getattr(pp, 'recommended_schema', []) or []
    content_angle = getattr(pp, 'content_angle', '') or ''
    diff_points = getattr(pp, 'differentiation_points', []) or []

    if gap_hints or rec_faq or content_angle:
        lines.append("")
        lines.append("COMPETITOR GAP INSIGHTS (observed from competitor analysis, use these to strengthen your content):")
        if gap_hints:
            lines.append("Must-cover topics competitors missed:")
            for g in gap_hints[:5]:
                lines.append(f"  - {g}")
        if rec_faq:
            lines.append("Recommended FAQ to include:")
            for f in rec_faq[:3]:
                lines.append(f"  - {f}")
        if rec_schema:
            lines.append(f"Recommended schema types: {', '.join(rec_schema)}")
        if content_angle:
            lines.append(f"Content differentiation angle: {content_angle}")
        if diff_points:
            lines.append("Key differentiation points:")
            for d in diff_points[:3]:
                lines.append(f"  - {d}")
        lines.append("IMPORTANT: Do NOT fabricate rankings or search volumes. Only reference observed gaps and inferred opportunities. Do not say 'top 10 competitors all...' without evidence.")

    return "\n".join(lines)


def _build_generation_prompt(page_plan: PagePlan, business_profile: BusinessProfile,
                             current_date: str) -> tuple:
    """构建 LLM 用的 system_prompt 和 user_prompt。"""
    pp = page_plan
    bp = business_profile or BusinessProfile()

    try:
        import run as _run
        skill = _run.llm.load_skill("seo-content")
    except Exception:
        skill = "You are an expert B2B SEO content writer. Output valid JSON."

    user_prompt = f"""Write a {pp.page_type} page for a B2B industrial website.

INDUSTRY: {bp.industry}
TARGET KEYWORD: {pp.primary_keyword}
PAGE TYPE: {pp.page_type}
LANGUAGE: {bp.languages[0] if bp.languages else 'English'}
TONE: {bp.tone or 'Professional, factual'}
CURRENT DATE: {current_date}

Create the page with title, meta_description (150-160 chars), html (well-structured with h2/h3 headings), and an image_query for a relevant photo."""

    schema_def = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "meta_description": {"type": "string"},
            "html": {"type": "string"},
            "image_query": {"type": "string"},
        },
        "required": ["title", "meta_description", "html"],
    }

    return skill, user_prompt, schema_def


def generate_page_content(page_plan, business_profile=None,
                          blueprint=None, current_date=None) -> PageContent:
    """从 PagePlan 生成 PageContent。

    Args:
        page_plan: PagePlan (或 dict with same keys)
        business_profile: BusinessProfile
        blueprint: SiteBlueprint (for context)
        current_date: str 或 None (默认今天)

    Returns:
        PageContent with body_html filled
    """
    if isinstance(page_plan, dict):
        page_plan = PagePlan.from_dict(page_plan)
    if business_profile is None:
        business_profile = BusinessProfile()
    if isinstance(business_profile, dict):
        business_profile = BusinessProfile.from_dict(business_profile)
    if current_date is None:
        current_date = datetime.date.today().strftime("%Y-%m-%d")

    pp = page_plan
    bp = business_profile

    system_prompt, user_prompt, schema_def = _build_generation_prompt(pp, bp, current_date)

    import run as _run
    content = _run._call_llm_with_retry(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_def=schema_def,
        page_label=f"[{pp.page_type}] {pp.primary_keyword}",
        page_type=pp.page_type,
        page_slug=pp.slug,
        target_kw=pp.primary_keyword,
    )

    return PageContent(
        slug=pp.slug,
        title=content.get("title", pp.title),
        page_type=pp.page_type,
        primary_keyword=pp.primary_keyword,
        secondary_keywords=list(pp.secondary_keywords),
        meta_title=content.get("title", ""),
        meta_description=content.get("meta_description", ""),
        body_html=content.get("html", ""),
        internal_links=list(pp.internal_links),
        source_page_plan=pp.slug,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def generate_pages_from_blueprint(blueprint, business_profile=None,
                                   max_workers=3) -> list[PageContent]:
    """从 SiteBlueprint 逐页生成所有 PageContent。

    当前串行执行(max_workers 参数预留)。
    每个页面失败不中断整体。
    """
    if isinstance(blueprint, dict):
        blueprint = SiteBlueprint.from_dict(blueprint)
    if business_profile is None:
        business_profile = blueprint.business_profile
    if isinstance(business_profile, dict):
        business_profile = BusinessProfile.from_dict(business_profile)

    results = []
    current_date = datetime.date.today().strftime("%Y-%m-%d")

    for pp in blueprint.pages:
        try:
            pc = generate_page_content(pp, business_profile, blueprint, current_date)
            results.append(pc)
        except Exception as e:
            # 失败页: 返回最小 PageContent 标记错误
            results.append(PageContent(
                slug=pp.slug,
                title=pp.title or pp.primary_keyword,
                page_type=pp.page_type,
                primary_keyword=pp.primary_keyword,
                review_status="failed",
                source_page_plan=pp.slug,
                created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            ))

    return results
