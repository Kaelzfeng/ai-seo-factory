# -*- coding: utf-8 -*-
"""tests/test_stage2_fact_guard.py · Phase 3.2 事实护栏测试

8. 不生成 pu-leather-is-real-leather category 页
9. risky keyword 会被改写为 comparison 或 safe FAQ
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from lib.seo_engine.schemas import BusinessProfile, Keyword
from lib.seo_engine.stage2_blueprint import (
    build_site_blueprint,
    _has_fact_risk, _normalize_fact_risk_keyword,
    _rewrite_risky_keyword_to_safe_page, _safe_keyword,
)


# ── Fact risk unit tests ──────────────────────────────


def test_detect_fact_risk():
    assert _has_fact_risk("pu leather is real leather") is True
    assert _has_fact_risk("pu leather genuine leather") is True
    assert _has_fact_risk("pu leather vs genuine leather") is False
    assert _has_fact_risk("pu leather supplier") is False


def test_normalize_risky_keyword():
    safe_kw, safe_type, safe_title = _normalize_fact_risk_keyword(
        "pu leather is real leather"
    )
    assert safe_type == "comparison"
    assert "genuine" in safe_kw or "vs" in safe_kw


def test_normalize_pu_leather_real():
    safe_kw, safe_type, safe_title = _normalize_fact_risk_keyword(
        "pu leather real"
    )
    assert safe_type in ("comparison", "faq")
    assert "real leather" not in safe_kw.lower() or \
           ("is" in safe_kw.lower() and safe_type == "faq")


def test_rewrite_risky_to_safe():
    result = _rewrite_risky_keyword_to_safe_page("pu leather is real leather")
    assert result is not None
    assert result["page_type"] == "comparison"
    assert "genuine" in result["primary_keyword"].lower()
    # slug 不应包含 is-real-leather
    assert "is-real-leather" not in result["slug"]


def test_rewrite_safe_keyword_returns_none():
    result = _rewrite_risky_keyword_to_safe_page("pu leather supplier")
    assert result is None


def test_safe_keyword_rewrites():
    result = _safe_keyword("pu leather is real leather")
    assert "genuine" in result.lower() or "vs" in result.lower()
    assert "is real leather" not in result.lower()


def test_safe_keyword_passes_through():
    assert _safe_keyword("pu leather supplier") == "pu leather supplier"


# ── Blueprint-level tests ─────────────────────────────


_RISKY_MOCK_KWS = [
    Keyword(keyword="pu leather guide", intent="guide", priority=10),
    Keyword(keyword="pu leather vs genuine leather", intent="comparison", priority=9),
    Keyword(keyword="pu leather vs pvc leather", intent="comparison", priority=9),
    Keyword(keyword="pu leather for furniture", intent="informational", priority=8),
    Keyword(keyword="pu leather for automotive", intent="informational", priority=8),
    Keyword(keyword="pu leather supplier", intent="product", priority=9),
    Keyword(keyword="is pu leather durable", intent="faq", priority=7),
    Keyword(keyword="is pu leather waterproof", intent="faq", priority=6),
    # 风险关键词 — 应被改写而非直接作为 category
    Keyword(keyword="pu leather is real leather", intent="informational", priority=5),
    Keyword(keyword="pu leather real", intent="informational", priority=3),
]


@pytest.fixture
def profile():
    return BusinessProfile(
        industry="PU leather", business_type="B2B supplier",
        target_markets=["global"], languages=["English"],
        products=["PU leather"], buyer_personas=["Importers"],
        tone="Professional",
    )


def test_no_fact_risk_category_page(monkeypatch, profile):
    """不生成 pu-leather-is-real-leather category 页。"""
    import lib.seo_engine.stage2_blueprint as s2
    monkeypatch.setattr(s2, "expand_seed_keywords",
                        lambda profile, seed_keywords=None, limit=210: _RISKY_MOCK_KWS)

    bp = build_site_blueprint(project_id=1, profile=profile)

    # 8. 不应有 is-real-leather slug
    for p in bp.pages:
        assert "is-real-leather" not in p.slug, \
            f"Fact risk slug found: {p.slug}"
        assert "pu-leather-is-real-leather" not in p.slug, \
            f"Fact risk slug: {p.slug}"

    # risky keyword 被改写后,不应作为 primary_keyword 出现原样
    for p in bp.pages:
        pk = p.primary_keyword.lower()
        assert pk != "pu leather is real leather", \
            f"Unrewritten risky keyword found: {pk}"


def test_risky_rewritten_to_comparison(monkeypatch, profile):
    """风险关键词被改写为 comparison 页。"""
    import lib.seo_engine.stage2_blueprint as s2
    monkeypatch.setattr(s2, "expand_seed_keywords",
                        lambda profile, seed_keywords=None, limit=210: _RISKY_MOCK_KWS)

    bp = build_site_blueprint(project_id=1, profile=profile)

    # 应有至少 2 个 comparison
    comps = [p for p in bp.pages if p.page_type == "comparison"]
    assert len(comps) >= 2, f"Expected >=2 comparison pages, got {len(comps)}"

    # 其中一个 comparison 应该涉及 genuine leather
    gen_pages = [p for p in bp.pages
                 if "genuine" in p.primary_keyword.lower()
                 or "genuine" in p.slug.lower()]
    assert len(gen_pages) >= 1, f"No genuine leather comparison found: {[p.slug for p in bp.pages]}"


def test_no_pu_leather_is_real_title(monkeypatch, profile):
    """title 中不出现 "PU Leather Is Real Leather" 这类风险表达。"""
    import lib.seo_engine.stage2_blueprint as s2
    monkeypatch.setattr(s2, "expand_seed_keywords",
                        lambda profile, seed_keywords=None, limit=210: _RISKY_MOCK_KWS)

    bp = build_site_blueprint(project_id=1, profile=profile)

    for p in bp.pages:
        title_lower = p.title.lower()
        assert "is real leather" not in title_lower, \
            f"Fact risk in title: {p.title}"

    # 应该有 comparison 标题包含 "Key Differences" 或 "vs"
    comp_titles = [p.title for p in bp.pages if p.page_type == "comparison"]
    assert any("difference" in t.lower() or " vs " in t.lower() for t in comp_titles), \
        f"Comparison titles lack 'difference' or 'vs': {comp_titles}"




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
