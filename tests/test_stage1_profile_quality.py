# -*- coding: utf-8 -*-
"""tests/test_stage1_profile_quality.py · Phase 3.1 Profile 质量测试

15. BusinessProfile fallback 包含 products / buyer_personas / terminology
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

# 阻止 LLM 调用
import lib.seo_engine.stage1_profile as s1_module


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    monkeypatch.setattr(s1_module, "_llm_enrich", lambda p: None)


from lib.seo_engine.stage1_profile import build_business_profile
from lib.seo_engine.schemas import BusinessProfile


def test_pu_leather_profile_has_products():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert len(profile.products) >= 3, f"Expected >=3 products, got {len(profile.products)}: {profile.products}"
    assert any("furniture" in p.lower() for p in profile.products), "Missing furniture product"
    assert any("automotive" in p.lower() for p in profile.products), "Missing automotive product"


def test_pu_leather_profile_has_buyer_personas():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert len(profile.buyer_personas) >= 2, f"Expected >=2 personas, got {len(profile.buyer_personas)}"
    assert any("furniture" in p.lower() or "manufacturer" in p.lower() for p in profile.buyer_personas)


def test_pu_leather_profile_has_terminology():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert len(profile.terminology) >= 4, f"Expected >=4 terms, got {len(profile.terminology)}: {profile.terminology}"
    assert any("abrasion" in t.lower() or "GSM" in t for t in profile.terminology)


def test_pu_leather_profile_business_type():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert "B2B" in profile.business_type or "supplier" in profile.business_type.lower()


def test_pu_leather_profile_tone_not_empty():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert len(profile.tone) > 10, f"Tone too short: {profile.tone}"


def test_generic_industry_has_fallback():
    """非特定行业也有通用 fallback。"""
    scope = {"industry": "UnknownWidget", "language": "English", "target_market": "global"}
    profile = build_business_profile(scope)
    assert len(profile.products) >= 1
    assert len(profile.buyer_personas) >= 1
    assert len(profile.terminology) >= 1


def test_profile_has_value_propositions():
    scope = {"industry": "PU leather", "language": "English", "target_market": "global B2B export"}
    profile = build_business_profile(scope)
    assert len(profile.value_propositions) >= 2, f"Expected >=2 VPs, got {profile.value_propositions}"
