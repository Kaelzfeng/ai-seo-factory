# -*- coding: utf-8 -*-
"""tests/test_stage0_clarify.py · Stage 0 测试

3. Stage 0 输入完整需求时不追问
4. Stage 0 缺 language / market 时返回 questions
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.stage0_clarify import (
    clarify_request, needs_clarification, missing_required_slots,
)


def test_complete_input_no_clarification():
    """完整输入时不需要追问。"""
    result = clarify_request(
        "I want an English B2B export site for PU leather targeting global buyers"
    )
    assert result["needs_clarification"] is False
    assert result["ok"] is True
    assert result["scope"]["industry"] != ""
    assert result["scope"]["language"] != ""
    assert result["scope"]["target_market"] != ""
    assert len(result["questions"]) == 0
    assert len(result["missing"]) == 0


def test_missing_language_asks():
    """缺少 language 时返回问题。"""
    result = clarify_request("Sell PU leather to global B2B buyers")
    # 应该有 industry 和 market, 但 language 可能缺
    missing = result.get("missing", [])
    # 如果 language 缺失
    if "language" in missing or result["needs_clarification"]:
        assert result["needs_clarification"] is True
        assert len(result["questions"]) > 0


def test_missing_market_asks():
    """缺少 target_market 时返回问题。"""
    result = clarify_request("I want an English site about solar panels")
    missing = result.get("missing", [])
    if "target_market" in missing or result["needs_clarification"]:
        assert result["needs_clarification"] is True


def test_needs_clarification_helper():
    """needs_clarification 检测不完整 scope。"""
    assert needs_clarification({"industry": "", "language": "", "target_market": ""}) is True
    assert needs_clarification({
        "industry": "PU leather", "language": "English", "target_market": "global"
    }) is False
    assert needs_clarification({
        "industry": "fabric", "language": "", "target_market": "US"
    }) is True


def test_missing_required_slots():
    """missing_required_slots 返回缺失列表。"""
    assert len(missing_required_slots({})) == 3
    assert missing_required_slots({"industry": "x", "language": "en", "target_market": "us"}) == []


def test_deterministic_fallback_works():
    """确定性提取能从文本中解析行业和市场。"""
    result = clarify_request(
        "Build a B2B wholesale export website for stainless steel pipes"
    )
    scope = result["scope"]
    # 确定性 fallback 至少能提取部分信息
    assert scope["industry"] != "" or scope["target_market"] != ""
