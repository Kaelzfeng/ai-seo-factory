# -*- coding: utf-8 -*-
"""tests/test_competitor_blueprint_hints.py · Phase 5.1 竞品反哺测试"""

import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.surpass_strategy import strategy_to_blueprint_hints, SurpassStrategy


def _mock_strategy():
    return SurpassStrategy(
        target_keyword="PU leather supplier",
        recommended_pages=["pu-leather-supplier", "pu-leather-vs-pvc", "pu-leather-guide"],
        recommended_sections=["Export process", "Quality certifications", "Customization options"],
        recommended_faq=["What is the MOQ for PU leather?", "How to verify supplier quality?"],
        recommended_schema=["FAQPage", "Organization", "Product"],
        content_angle="Authoritative B2B sourcing guide with technical specs",
        differentiation_points=["Exceed depth", "Add certification details"],
        priority_score=74.0,
    )


def test_hints_returns_structured_pages():
    hints = strategy_to_blueprint_hints(_mock_strategy())
    pages = hints["recommended_pages"]
    assert len(pages) >= 1
    for p in pages:
        assert "slug" in p, f"Missing slug in {p}"
        assert "page_type" in p, f"Missing page_type in {p}"
        assert "primary_keyword" in p, f"Missing primary_keyword in {p}"
        assert "title" in p, f"Missing title in {p}"


def test_hints_has_sections_faq_schema():
    hints = strategy_to_blueprint_hints(_mock_strategy())
    assert len(hints["recommended_sections"]) > 0
    assert len(hints["recommended_faq"]) > 0
    assert len(hints["recommended_schema"]) > 0


def test_hints_has_keywords():
    hints = strategy_to_blueprint_hints(_mock_strategy())
    assert len(hints["recommended_keywords"]) > 0


def test_hints_page_type_inference():
    hints = strategy_to_blueprint_hints(_mock_strategy())
    for p in hints["recommended_pages"]:
        assert p["page_type"] in (
            "article", "comparison", "faq", "product", "guide", "category"
        ), f"Invalid page_type: {p['page_type']}"


def test_hints_not_empty():
    hints = strategy_to_blueprint_hints(_mock_strategy())
    assert hints["recommended_pages"]
    assert hints["priority_score"] > 0
    assert hints["content_angle"]
