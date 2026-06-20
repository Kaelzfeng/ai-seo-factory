# -*- coding: utf-8 -*-
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.competitor_schema import CompetitorProfile, GapMatrix
from lib.gap_analyzer import build_gap_matrix, prioritize_gaps


def _mock_profiles():
    return [
        CompetitorProfile(domain="a.com", keywords=["pu leather", "supplier", "vs genuine"],
                          schema_types=["Article", "FAQPage"],
                          faq_items=[{"question": "Is PU leather durable?"}],
                          content_depth_score=70,
                          raw_signals=None, weaknesses=[]),
        CompetitorProfile(domain="b.com", keywords=["pu leather", "wholesale", "for furniture"],
                          schema_types=["Article"],
                          faq_items=[{"question": "How to choose PU leather?"}],
                          content_depth_score=50,
                          raw_signals=None, weaknesses=[]),
    ]


def test_build_gap_matrix_keyword_gaps():
    gm = build_gap_matrix(_mock_profiles())
    assert len(gm.keyword_gaps) > 0


def test_build_gap_matrix_schema_gaps():
    gm = build_gap_matrix(_mock_profiles())
    assert len(gm.schema_gaps) > 0


def test_build_gap_matrix_faq_gaps():
    gm = build_gap_matrix(_mock_profiles())
    assert len(gm.faq_gaps) > 0


def test_prioritize_gaps():
    gm = build_gap_matrix(_mock_profiles())
    items = prioritize_gaps(gm)
    assert len(items) > 0
    # first item should have highest priority
    assert items[0]["priority"] >= items[-1]["priority"]
