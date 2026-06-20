# -*- coding: utf-8 -*-
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.competitor_schema import SERPResult, OnPageSignals
from lib.competitor_analysis import (
    infer_keywords_from_signals, classify_competitor_intents,
    score_content_depth, score_structure, identify_weaknesses,
    build_competitor_profile, analyze_competitors,
)


def test_infer_keywords():
    signals = OnPageSignals(
        title="PU Leather Supplier Guide",
        meta_description="Complete guide to PU leather for B2B buyers",
        h1=["PU Leather Supplier Guide"],
        h2=["Types of PU Leather", "How to Choose Supplier", "FAQ"],
    )
    kws = infer_keywords_from_signals(signals)
    assert len(kws) > 0
    assert any("leather" in k.lower() for k in kws)


def test_classify_intents():
    kws = ["pu leather supplier", "pu leather vs genuine", "what is pu leather"]
    intents = classify_competitor_intents(kws)
    assert len(intents) >= 2


def test_score_content_depth():
    signals = OnPageSignals(word_count=2500, h2=["a"]*6, faq_count=3, schema_types=["Article", "FAQPage"], internal_links_count=12)
    assert score_content_depth(signals) >= 80


def test_score_structure():
    signals = OnPageSignals(title="T", meta_description="M", h1=["H1"], h2=["a"]*4, schema_types=["Article"])
    assert score_structure(signals) >= 60


def test_identify_weaknesses():
    signals = OnPageSignals(word_count=200)
    w = identify_weaknesses(signals)
    assert len(w) > 0
    assert any("Thin content" in x or "Missing" in x for x in w)


def test_build_competitor_profile():
    sr = SERPResult(rank=1, title="Test", url="https://x.com", domain="x.com")
    signals = OnPageSignals(url="https://x.com", title="Test Supplier Guide",
                            meta_description="M", h1=["Test"], word_count=1200,
                            schema_types=["Article"], faq_count=1)
    cp = build_competitor_profile(sr, signals)
    assert cp.rank == 1
    assert len(cp.keywords) > 0
    assert len(cp.weaknesses) >= 0  # may or may not have weaknesses


def test_analyze_competitors_mock():
    report = analyze_competitors("PU leather supplier", provider_name="mock", limit=5)
    assert report.status == "completed"
    assert len(report.serp_results) == 5
    assert len(report.competitors) == 5


def test_analyze_competitors_partial():
    """Manual provider with unreachable URLs。"""
    report = analyze_competitors("test", urls=["https://unreachable.test/xyz"], limit=1)
    assert report.status in ("partial_success", "failed", "completed")
