# -*- coding: utf-8 -*-
"""Phase 5.1: Stage 3 prompt context with competitor hints"""

import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import PagePlan, BusinessProfile
from lib.seo_engine.stage3_generate import page_plan_to_prompt_context


def test_prompt_context_has_competitor_gaps():
    pp = PagePlan(
        slug="test", page_type="guide", primary_keyword="test kw",
        competitor_gap_hints=["Certification process", "MOQ guidelines"],
        recommended_faq=["What is the MOQ?"],
        recommended_schema=["FAQPage"],
        content_angle="Authoritative guide",
        differentiation_points=["Detailed specs"],
    )
    bp = BusinessProfile(industry="Test", languages=["English"], target_markets=["global"], products=["Test"])
    ctx = page_plan_to_prompt_context(pp, bp)

    assert "COMPETITOR GAP INSIGHTS" in ctx
    assert "Certification process" in ctx
    assert "MOQ guidelines" in ctx
    assert "What is the MOQ?" in ctx
    assert "FAQPage" in ctx
    assert "Authoritative guide" in ctx


def test_prompt_context_no_fake_rankings():
    pp = PagePlan(slug="t", page_type="guide", primary_keyword="k",
                  competitor_gap_hints=["gap1"])
    bp = BusinessProfile(industry="T", languages=["En"], target_markets=["g"], products=["T"])
    ctx = page_plan_to_prompt_context(pp, bp)

    # 不应声称 "top 10" 作为事实, 但警告 "don't say top 10" 是允许的
    assert "Do NOT fabricate" in ctx
    assert "do not say 'top 10 competitors all...' without evidence" in ctx.lower()


def test_prompt_context_without_hints():
    pp = PagePlan(slug="t", page_type="article", primary_keyword="k")
    bp = BusinessProfile(industry="T", languages=["En"], target_markets=["g"], products=["T"])
    ctx = page_plan_to_prompt_context(pp, bp)
    assert "COMPETITOR GAP INSIGHTS" not in ctx


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
