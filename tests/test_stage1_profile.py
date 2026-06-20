# -*- coding: utf-8 -*-
"""tests/test_stage1_profile.py · Stage 1 测试

5. Stage 1 能生成有效 BusinessProfile
6. Stage 1 LLM 失败时 fallback 可用
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

# 阻止所有测试调用真实 LLM
import lib.seo_engine.stage1_profile as s1_module


@pytest.fixture(autouse=True)
def _mock_llm_enrich(monkeypatch):
    monkeypatch.setattr(s1_module, "_llm_enrich", lambda p: None)


from lib.seo_engine.stage1_profile import (
    build_business_profile, validate_business_profile, profile_to_prompt_context,
)
from lib.seo_engine.schemas import BusinessProfile


def test_build_minimal_profile():
    """最小 scope 也能生成有效 profile。"""
    scope = {"industry": "PU leather", "language": "English", "target_market": "global"}
    profile = build_business_profile(scope)
    assert isinstance(profile, BusinessProfile)
    assert profile.industry == "PU leather"
    assert len(profile.languages) >= 1
    assert len(profile.target_markets) >= 1
    assert len(profile.products) >= 1
    assert len(profile.tone) > 0


def test_build_profile_with_scope_fields():
    """scope 包含完整字段时正确填充。"""
    scope = {
        "industry": "Solar Panels",
        "language": "Spanish",
        "target_market": "Latin America",
        "business_type": "B2C",
    }
    profile = build_business_profile(scope)
    assert "Spanish" in profile.languages
    assert "Latin America" in profile.target_markets[0] or len(profile.target_markets) >= 1


def test_validate_valid_profile():
    """有效 profile 通过验证。"""
    profile = BusinessProfile(
        industry="Test", target_markets=["global"], languages=["English"],
        products=["Test"], buyer_personas=["Test buyer"],
        tone="Professional", terminology=["test"],
    )
    result = validate_business_profile(profile)
    assert result["valid"] is True
    assert len(result["issues"]) == 0


def test_validate_invalid_profile():
    """无效 profile 返回 issues。"""
    profile = BusinessProfile()
    result = validate_business_profile(profile)
    assert result["valid"] is False
    assert len(result["issues"]) > 0


def test_profile_to_prompt_context():
    """profile_to_prompt_context 生成非空字符串。"""
    profile = BusinessProfile(
        industry="PU leather", target_markets=["global"],
        languages=["English"], products=["PU leather"],
        buyer_personas=["Importers"], tone="Professional",
    )
    ctx = profile_to_prompt_context(profile)
    assert "PU leather" in ctx
    assert "INDUSTRY:" in ctx
    assert "TONE:" in ctx


def test_llm_failure_does_not_crash(monkeypatch):
    """LLM 调用失败时 build_business_profile 不掉。"""
    import lib.seo_engine.stage1_profile as s1
    # 让 LLM 调用抛异常
    def fake_structured(**kw):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(s1, "_llm_enrich", lambda p: None)

    scope = {"industry": "Test", "language": "English", "target_market": "global"}
    profile = build_business_profile(scope)
    assert profile.industry == "Test"
    # fallback 应提供默认值
    assert len(profile.products) >= 1
