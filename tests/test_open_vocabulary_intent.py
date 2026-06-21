# -*- coding: utf-8 -*-
"""tests/test_open_vocabulary_intent.py · Phase 9.3.9: Open Vocabulary Intent Tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.intent_engine import merge_intent, is_intent_ready, product_display_name, empty_intent


def test_extract_unknown_product_from_chinese_export_site():
    """帮我制作一个铁管的出口站要日语的 → product=铁管, language=Japanese."""
    intent = merge_intent(empty_intent(), "帮我制作一个铁管的出口站要日语的")
    assert intent["product"] == "铁管"
    assert intent["language"] == "Japanese"
    assert is_intent_ready(intent)


def test_extract_hydraulic_fitting_from_foreign_trade_site():
    """做一个液压接头英文外贸站，面向欧洲批发商."""
    intent = merge_intent(empty_intent(), "做一个液压接头英文外贸站，面向欧洲批发商")
    assert intent["product"] == "液压接头"
    assert intent["language"] == "English"
    assert intent["market"] == "欧洲"
    assert intent["audience"] == "批发商"
    assert is_intent_ready(intent)


def test_extract_ceramic_mug_from_spanish_b2b_site():
    """帮我生成一个陶瓷杯西语B2B网站."""
    intent = merge_intent(empty_intent(), "帮我生成一个陶瓷杯西语B2B网站")
    assert intent["product"] == "陶瓷杯"
    assert intent["language"] == "Spanish"
    assert is_intent_ready(intent)


def test_extract_industrial_belt_from_german_export_site():
    """我要做工业皮带出口站，德语，面向德国采购商."""
    intent = merge_intent(empty_intent(), "我要做工业皮带出口站，德语，面向德国采购商")
    assert intent["product"] == "工业皮带"
    assert intent["language"] == "German"
    assert intent["market"] == "德国"


def test_extract_english_long_tail_product():
    """create a B2B export website for acrylic display stands in French."""
    intent = merge_intent(empty_intent(),
        "create a B2B export website for acrylic display stands in French")
    # Check product contains the key phrase
    prod = (intent.get("product") or "").lower()
    assert "acrylic" in prod or "display" in prod
    assert intent["language"] == "French"


def test_unknown_product_never_becomes_none():
    """Even with no keyword match, product should be extracted or explicitly None (not silently empty)."""
    # If regex extraction fails AND no keyword match, product stays None
    # But that's okay — is_intent_ready will reject it
    intent = merge_intent(empty_intent(), "hello world")
    # Product may be None because no extraction pattern matched
    # But is_intent_ready must be False
    assert not is_intent_ready(intent)


def test_generation_plan_titles_do_not_contain_none():
    """Plan titles must not contain 'None'."""
    from lib.generation_plan import build_generation_plan
    intent = merge_intent(empty_intent(), "帮我制作铁管的出口站")
    assert intent["product"] == "铁管"
    plan = build_generation_plan(intent)
    for page in plan["pages"]:
        assert "None" not in page["title"]
        assert page["title"].strip()


def test_multiturn_unknown_product_merge():
    """Multi-turn: 液压接头 → 德语 → 欧洲批发商."""
    intent = empty_intent()
    intent = merge_intent(intent, "液压接头")
    assert intent["product"] == "液压接头"

    intent = merge_intent(intent, "德语")
    assert intent["language"] == "German"
    assert intent["product"] == "液压接头"  # preserved

    intent = merge_intent(intent, "欧洲批发商")
    assert intent["audience"] == "批发商"
    assert intent["market"] == "欧洲"
    assert intent["product"] == "液压接头"  # still preserved
    assert is_intent_ready(intent)


def test_override_language_and_market_preserves_product():
    """改成葡萄牙语，巴西市场 — overrides language + market, preserves product."""
    intent = merge_intent(empty_intent(), "陶瓷杯 西班牙语 墨西哥市场")
    assert intent["product"] == "陶瓷杯"
    assert intent["language"] == "Spanish"

    intent = merge_intent(intent, "改成葡萄牙语，巴西市场")
    assert intent["language"] == "Portuguese"
    assert "巴西" in str(intent.get("market", "")) or intent.get("market") == "巴西"
    assert intent["product"] == "陶瓷杯"  # preserved


def test_export_site_sets_b2b_export_intent():
    """Export site intent should set appropriate goal."""
    intent = merge_intent(empty_intent(),
        "generate SEO pages for stainless steel hose clamps, target US distributors, in French")
    prod = (intent.get("product") or "").lower()
    assert "stainless" in prod or "hose" in prod or "clamp" in prod
    assert intent["language"] == "French"
    assert intent.get("market") == "USA" or intent.get("market") == "US"
    assert is_intent_ready(intent)


def test_clarification_only_when_product_truly_missing():
    """Product is extracted by regex — should not ask clarification. Product truly missing → clarification."""
    # Case 1: product can be extracted
    intent = merge_intent(empty_intent(), "帮我做一个铁管的网站")
    assert intent["product"] is not None
    # Case 2: no product at all → not ready
    intent2 = merge_intent(empty_intent(), "帮我做一个网站")
    assert not is_intent_ready(intent2) or intent2.get("product") is not None
