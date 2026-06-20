# -*- coding: utf-8 -*-
"""tests/test_competitor_schema.py · Schema serialization"""

import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.competitor_schema import (
    SERPResult, OnPageSignals, CompetitorProfile, GapMatrix,
    SurpassStrategy, CompetitorReport,
)


def test_serp_result_roundtrip():
    s = SERPResult(rank=1, title="Test", url="https://x.com", domain="x.com")
    d = s.to_dict()
    s2 = SERPResult.from_dict(d)
    assert s2.rank == 1
    assert s2.url == "https://x.com"


def test_onpage_signals_roundtrip():
    o = OnPageSignals(url="https://x.com", title="T", word_count=500, h1=["H1"])
    d = o.to_dict()
    o2 = OnPageSignals.from_dict(d)
    assert o2.word_count == 500
    assert o2.h1 == ["H1"]


def test_competitor_profile_roundtrip():
    sig = OnPageSignals(url="https://x.com", title="T", word_count=500)
    cp = CompetitorProfile(domain="x.com", url="https://x.com", rank=1,
                           title="T", raw_signals=sig, weaknesses=["Missing H1"])
    d = cp.to_dict()
    cp2 = CompetitorProfile.from_dict(d)
    assert cp2.weaknesses == ["Missing H1"]
    assert cp2.raw_signals.word_count == 500


def test_competitor_report_roundtrip():
    report = CompetitorReport(
        query="test", status="completed",
        serp_results=[SERPResult(rank=1, title="T", url="https://x.com", domain="x.com")],
        competitors=[CompetitorProfile(domain="x.com", url="https://x.com", rank=1)],
        gap_matrix=GapMatrix(keyword_gaps=["kw1"]),
        surpass_strategy=SurpassStrategy(target_keyword="test", recommended_pages=["p1"]),
    )
    d = report.to_dict()
    r2 = CompetitorReport.from_dict(d)
    assert r2.query == "test"
    assert len(r2.serp_results) == 1
    assert r2.gap_matrix.keyword_gaps == ["kw1"]
    assert r2.surpass_strategy.target_keyword == "test"
