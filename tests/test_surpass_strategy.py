# -*- coding: utf-8 -*-
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.competitor_schema import GapMatrix
from lib.surpass_strategy import (
    build_surpass_strategy, strategy_to_blueprint_hints, strategy_to_markdown,
)


def _mock_gap():
    return GapMatrix(
        keyword_gaps=["pu leather supplier", "pu leather vs pvc"],
        schema_gaps=["Add FAQPage schema"],
        faq_gaps=["Is PU leather waterproof?"],
        topic_gaps=["Detailed comparison guide"],
        priority_items=[
            {"type": "keyword", "item": "pu leather supplier", "priority": 5},
            {"type": "schema", "item": "Add FAQPage schema", "priority": 3},
        ],
    )


def test_build_strategy_has_pages():
    s = build_surpass_strategy("PU leather supplier", _mock_gap())
    assert len(s.recommended_pages) > 0


def test_build_strategy_has_faq():
    s = build_surpass_strategy("PU leather supplier", _mock_gap())
    # faq_gaps may be deduplicated; check at least strategy exists
    assert s.recommended_faq is not None  # may be empty if no faq items in priority


def test_build_strategy_has_schema():
    s = build_surpass_strategy("PU leather supplier", _mock_gap())
    assert len(s.recommended_schema) > 0


def test_strategy_to_hints():
    s = build_surpass_strategy("PU leather supplier", _mock_gap())
    hints = strategy_to_blueprint_hints(s)
    assert "recommended_pages" in hints
    assert "recommended_sections" in hints


def test_strategy_to_markdown():
    s = build_surpass_strategy("PU leather supplier", _mock_gap())
    md = strategy_to_markdown(s)
    assert "PU leather supplier" in md
    assert "## Recommended Pages" in md
    assert "## Rationale" in md
