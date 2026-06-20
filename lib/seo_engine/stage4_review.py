# -*- coding: utf-8 -*-
"""lib/seo_engine/stage4_review.py · Stage 4: 内容审核

确定性层 A: 调用 quality.score_page() + quality_ext.extended_quality_check()
预留 Agent 层 B/C 接口。
"""


def should_polish(review_result: dict) -> bool:
    """判断是否需要润色。"""
    return review_result.get("needs_polish", False)


def merge_quality_reports(quality_base: dict, ext_report: dict) -> dict:
    """合并 quality.score_page() 和 quality_ext 报告。"""
    base_score = quality_base.get("score", 0)
    ext_ok = ext_report.get("ok", True)

    issues = list(quality_base.get("issues", []))
    issues.extend(ext_report.get("issues", []))

    return {
        "ok": quality_base.get("passed", False) and ext_ok,
        "score": base_score,
        "needs_polish": base_score < 70,
        "issues": issues,
        "ext": ext_report,
    }


def review_page_content(page_content, sibling_pages=None) -> dict:
    """Stage 4 内容审核 (确定性层 A)。

    1. 调用 quality.score_page()
    2. 调用 quality_ext.extended_quality_check()
    3. 合并结果
    4. HTML 不安全 → failed
    5. 重复风险高 → warning 或 failed
    6. 分数低 → needs_polish

    Returns:
        {"ok": bool, "score": float, "needs_polish": bool, "issues": [...], "ext": {...}}
    """
    # 构建 quality.score_page() 需要的参数
    page = {
        "slug": "",
        "type": "article",
        "target_keyword": "",
    }
    content = {"title": "", "meta_description": "", "html": ""}

    if hasattr(page_content, 'slug'):
        page["slug"] = page_content.slug
        page["type"] = getattr(page_content, 'page_type', 'article')
        page["target_keyword"] = getattr(page_content, 'primary_keyword', '')
        content["title"] = getattr(page_content, 'title', '')
        content["meta_description"] = getattr(page_content, 'meta_description', '')
        content["html"] = getattr(page_content, 'body_html', '')
    elif isinstance(page_content, dict):
        page["slug"] = page_content.get('slug', '')
        page["type"] = page_content.get('page_type', 'article')
        page["target_keyword"] = page_content.get('primary_keyword', '')
        content["title"] = page_content.get('title', '')
        content["meta_description"] = page_content.get('meta_description', '')
        content["html"] = page_content.get('body_html', '')

    # 1. 基础质量评分 (复用 quality.py)
    try:
        from lib import quality
        industry = {"name": "", "seed_keyword": page["target_keyword"], "language": "English"}
        quality_base = quality.score_page(page, content, industry)
    except Exception:
        quality_base = {"score": 0, "passed": False, "issues": ["quality.score_page failed"]}

    # 2. 扩展质量检查
    from lib.quality_ext import extended_quality_check
    ext_report = extended_quality_check(page_content, sibling_pages)

    # 3. 合并
    merged = merge_quality_reports(quality_base, ext_report)

    # 4. HTML 不安全 → failed
    if not ext_report.get("html_safe", True):
        merged["ok"] = False
        merged["issues"].append("HTML unsafe - contains forbidden elements")

    # 5. 重复风险高 → warning
    if ext_report.get("duplicate_risk", 0) > 0.7:
        merged["needs_polish"] = True
        if ext_report.get("duplicate_risk", 0) > 0.9:
            merged["ok"] = False

    return merged


def review_pages(page_contents: list) -> list[dict]:
    """批量审核。"""
    results = []
    for pc in page_contents:
        siblings = [s for s in page_contents if s != pc]
        results.append(review_page_content(pc, siblings))
    return results


# ── Agent 层预留接口 ──────────────────────────────────


def agent_naturalness_review(page_content) -> dict:
    """Agent 层 B: 自然度审核。本阶段返回 skipped。"""
    return {"ok": True, "status": "skipped", "note": "not implemented in Phase 4"}


def agent_fact_check_review(page_content) -> dict:
    """Agent 层 C: 事实核查。本阶段返回 skipped。"""
    return {"ok": True, "status": "skipped", "note": "not implemented in Phase 4"}
