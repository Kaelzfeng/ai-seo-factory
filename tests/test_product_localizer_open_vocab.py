# -*- coding: utf-8 -*-
"""tests/test_product_localizer_open_vocab.py · Phase 9.4.1
Open-vocabulary product localization tests.

Proves:
- Builtin glossary works as high-frequency fallback
- Open-vocab products can be translated via mock provider
- Products NOT in the glossary still work
- translation_missing is correctly marked
- product_original always preserved
- product_localized never polluted by market/language
- No None appears anywhere
- Provider is mockable (no network calls)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.product_localizer import (
    ProductLocalizationResult,
    MockTranslationProvider,
    TranslationProvider,
    _is_builtin_product,
    _lookup_glossary,
    assert_no_none_terms,
    build_product_translation_prompt,
    get_product_name_for_page,
    has_source_language_leak,
    localize_product_name,
    parse_product_translation_response,
    product_localization_coverage,
    product_translation_missing,
    source_language_leak_score,
    validate_product_translation,
)


# ═══════════════════════════════════════════════════════════
# Builtin glossary tests
# ═══════════════════════════════════════════════════════════

def test_localize_builtin_product_spanish_hydraulic_fitting():
    result = localize_product_name("液压接头", "Spanish")
    assert result.product_original == "液压接头"
    assert result.product_localized == "racores hidráulicos"
    assert result.target_language == "Spanish"
    assert result.method == "builtin_glossary"
    assert result.confidence >= 0.9
    assert not result.translation_missing


def test_localize_builtin_product_japanese_steel_pipe():
    result = localize_product_name("铁管", "Japanese")
    assert result.product_original == "铁管"
    assert result.product_localized in ("鉄管", "铁管")
    assert result.target_language == "Japanese"
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


def test_localize_builtin_product_german_industrial_belt():
    result = localize_product_name("工业皮带", "German")
    assert result.product_original == "工业皮带"
    assert result.product_localized == "Industriegurte"
    assert result.target_language == "German"
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


def test_localize_builtin_product_french_ceramic_mug():
    result = localize_product_name("陶瓷杯", "French")
    assert result.product_original == "陶瓷杯"
    assert result.product_localized == "tasses en céramique"
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


def test_localize_builtin_product_portuguese_pet_brush():
    result = localize_product_name("宠物梳", "Portuguese")
    assert result.product_original == "宠物梳"
    assert result.product_localized == "escova para animais de estimação"
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


def test_localize_builtin_cold_chain_indonesian():
    result = localize_product_name("冷链保温箱", "Indonesian")
    assert result.product_original == "冷链保温箱"
    assert result.product_localized == "kotak insulasi rantai dingin"
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


# ═══════════════════════════════════════════════════════════
# Open vocabulary tests with mock provider
# ═══════════════════════════════════════════════════════════

def test_open_vocab_product_graphite_crucible_german_mocked():
    """石墨坩埚 is NOT in the builtin glossary — provider must handle it."""
    assert not _is_builtin_product("石墨坩埚")

    mock = MockTranslationProvider()
    result = localize_product_name("石墨坩埚", "German", provider=mock)

    assert result.product_original == "石墨坩埚"
    assert result.product_localized == "Graphittiegel"
    assert result.target_language == "German"
    assert result.method == "llm_structured_translation"
    assert result.confidence == 0.88
    assert not result.translation_missing


def test_open_vocab_product_silicone_seal_french_mocked():
    """硅胶密封圈 is NOT in the builtin glossary."""
    assert not _is_builtin_product("硅胶密封圈")

    mock = MockTranslationProvider()
    result = localize_product_name("硅胶密封圈", "French", provider=mock)

    assert result.product_original == "硅胶密封圈"
    assert result.product_localized == "joints d'étanchéité en silicone"
    assert result.target_language == "French"
    assert result.method == "llm_structured_translation"
    assert result.confidence == 0.86
    assert not result.translation_missing


def test_open_vocab_product_anti_static_turnover_box_vietnamese_mocked():
    """anti-static turnover box is not in builtin glossary."""
    assert not _is_builtin_product("anti-static turnover box")

    mock = MockTranslationProvider()
    result = localize_product_name("anti-static turnover box", "Vietnamese", provider=mock)

    assert result.product_original == "anti-static turnover box"
    assert result.product_localized == "thùng chứa chống tĩnh điện"
    assert result.target_language == "Vietnamese"
    assert result.method == "llm_structured_translation"
    assert result.confidence == 0.84
    assert not result.translation_missing


def test_open_vocab_product_cold_chain_insulated_box_indonesian_mocked():
    """English version of 冷链保温箱 — in builtin glossary, no provider needed."""
    mock = MockTranslationProvider()
    result = localize_product_name("cold chain insulated box", "Indonesian", provider=mock)

    assert result.product_original == "cold chain insulated box"
    assert result.product_localized == "kotak insulasi rantai dingin"
    assert result.target_language == "Indonesian"
    # Found in builtin glossary (takes priority over provider)
    assert result.method == "builtin_glossary"
    assert not result.translation_missing


# ═══════════════════════════════════════════════════════════
# Translation failure handling
# ═══════════════════════════════════════════════════════════

def test_unknown_product_translation_failure_marks_missing():
    """A product not in glossary AND not in mock provider must mark missing."""
    mock = MockTranslationProvider()
    # "量子计算芯片" is not in glossary and not in mock
    result = localize_product_name("量子计算芯片", "German", provider=mock)

    assert result.product_original == "量子计算芯片"
    assert result.product_localized == "量子计算芯片"  # Falls back to original
    assert result.method == "fallback_original"
    assert result.translation_missing is True
    assert result.confidence == 0.0


def test_unknown_product_without_provider_marks_missing():
    """Without any provider, unknown product falls back to original."""
    result = localize_product_name("特种合金钻头", "French", provider=None)

    assert result.product_original == "特种合金钻头"
    assert result.method == "fallback_original"
    assert result.translation_missing is True


# ═══════════════════════════════════════════════════════════
# Product original preserved for audit
# ═══════════════════════════════════════════════════════════

def test_product_original_preserved_for_audit():
    """product_original must always keep the raw extracted name."""
    mock = MockTranslationProvider()

    # Builtin glossary case
    r1 = localize_product_name("液压接头", "Spanish")
    assert r1.product_original == "液压接头"
    assert r1.product_localized != "液压接头"

    # Open vocab via mock
    r2 = localize_product_name("石墨坩埚", "German", provider=mock)
    assert r2.product_original == "石墨坩埚"
    assert r2.product_localized == "Graphittiegel"

    # Translation failure
    r3 = localize_product_name("未知产品XYZ", "Japanese")
    assert r3.product_original == "未知产品XYZ"
    assert r3.translation_missing is True


def test_product_original_never_empty_or_none():
    """Even for edge cases, product_original should never be None."""
    mock = MockTranslationProvider()
    r = localize_product_name("", "Spanish", provider=mock)
    assert r.translation_missing
    assert r.product_localized == "Product"
    # product_original reflects what was passed
    assert r.product_original == ""


# ═══════════════════════════════════════════════════════════
# product_localized used in page titles and body
# ═══════════════════════════════════════════════════════════

def test_product_localized_used_in_page_title():
    """Page titles must use product_localized, not product_original."""
    from lib.intent_engine import empty_intent, merge_intent
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import localized_page_title

    intent = merge_intent(empty_intent(), "做一个液压接头西班牙语B2B出口站")
    # The localized product should be in the intent
    assert intent["product"] == "液压接头"
    assert intent["product_localized"] == "racores hidráulicos"

    brief = build_industry_brief(intent)
    title = localized_page_title(brief, "supplier_guide")

    # Title must use localized product
    assert "racores" in title.lower()
    # Title must NOT contain original Chinese product
    assert "液压接头" not in title
    assert "None" not in title


def test_product_localized_used_in_body():
    """Page body must use product_localized."""
    from lib.intent_engine import empty_intent, merge_intent
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    intent = merge_intent(empty_intent(), "做一个工业皮带德语外贸站")
    assert intent["product_localized"] == "Industriegurte"

    brief = build_industry_brief(intent)
    page = write_page_content({"type": "supplier_guide"}, brief)

    # Body should use the localized product
    assert "Industriegurte" in page["html"] or "Industriegurt" in page["html"]
    # Must not contain original Chinese
    assert "工业皮带" not in page["title"]
    assert "None" not in page["html"]
    assert "None" not in page["title"]


# ═══════════════════════════════════════════════════════════
# Language leak detection
# ═══════════════════════════════════════════════════════════

def test_non_chinese_target_page_does_not_mix_chinese_product_when_translation_available():
    """When product_localized is available, non-Chinese pages must not show the
    original Chinese product name in page titles or headings."""
    from lib.intent_engine import empty_intent, merge_intent
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    intent = merge_intent(empty_intent(), "做一个液压接头西班牙语B2B出口站")
    brief = build_industry_brief(intent)
    page = write_page_content({"type": "supplier_guide"}, brief)

    text = page["title"] + " " + page["html"]

    # Must use localized product
    assert "racores" in text.lower()

    # The original Chinese product name must NOT appear in the title
    assert "液压接头" not in page["title"]

    # The original Chinese product name should not dominate the body
    # (count occurrences — should be very few if any)
    body_count = page["html"].count("液压接头")
    assert body_count < 3, f"Chinese product name appears {body_count} times in body"


def test_source_language_leak_score_zero_when_clean():
    """A clean translated page should have zero leak score."""
    mock = MockTranslationProvider()
    result = localize_product_name("石墨坩埚", "German", provider=mock)
    clean_text = f"<h1>Lieferantenleitfaden für {result.product_localized}</h1><p>Spezifikationen für Graphittiegel.</p>"
    score = source_language_leak_score(clean_text, "石墨坩埚", "German")
    assert score == 0.0


def test_source_language_leak_score_detects_leak():
    """Text with Chinese characters in German page should be flagged."""
    leaky_text = "<h1>Lieferantenleitfaden für 石墨坩埚</h1><p>石墨坩埚 Spezifikationen</p>"
    score = source_language_leak_score(leaky_text, "石墨坩埚", "German")
    assert score > 0.0


def test_technical_acronyms_not_flagged_as_leak():
    """MOQ, OEM, BSP, NPT etc. should NOT trigger language leak."""
    text = (
        "<h1>Guía de proveedores de racores hidráulicos</h1>"
        "<p>BSP, NPT, JIC, DIN, ISO, FDA, CE, MOQ, OEM, ODM, ASTM</p>"
    )
    assert not has_source_language_leak(text, "Chinese", "Spanish")
    score = source_language_leak_score(text, "液压接头", "Spanish")
    assert score == 0.0


# ═══════════════════════════════════════════════════════════
# Market / language separation in product_localized
# ═══════════════════════════════════════════════════════════

def test_market_does_not_pollute_product_localized():
    """Market name must not appear in product_localized."""
    mock = MockTranslationProvider()
    result = localize_product_name(
        "石墨坩埚", "German", market="Germany", provider=mock
    )
    assert "Germany" not in result.product_localized
    assert "Deutschland" not in result.product_localized
    assert "deutsch" not in result.product_localized.lower()
    assert result.product_localized == "Graphittiegel"


def test_language_does_not_pollute_product_localized():
    """Language name must not appear in product_localized."""
    mock = MockTranslationProvider()
    result = localize_product_name(
        "硅胶密封圈", "French", provider=mock
    )
    assert "French" not in result.product_localized
    assert "Français" not in result.product_localized
    assert "franc" not in result.product_localized.lower()
    assert result.product_localized == "joints d'étanchéité en silicone"


def test_builtin_product_localized_does_not_contain_language_or_market():
    """All builtin glossary entries must be clean."""
    for product, translations in [
        ("液压接头", {"Spanish": "racores hidráulicos", "German": "Hydraulikanschlüsse"}),
        ("铁管", {"Japanese": "鉄管", "German": "Stahlrohre"}),
        ("陶瓷杯", {"French": "tasses en céramique", "Spanish": "tazas de cerámica"}),
    ]:
        for language, expected in translations.items():
            result = localize_product_name(product, language)
            assert result.product_localized == expected
            # No language name in result
            assert language not in result.product_localized
            assert "Germany" not in result.product_localized
            assert "Spain" not in result.product_localized


# ═══════════════════════════════════════════════════════════
# Provider mockability
# ═══════════════════════════════════════════════════════════

def test_translation_provider_is_mockable_no_network():
    """Prove that the provider pattern allows testing without network."""
    # MockProvider returns predefined results without any network calls
    mock = MockTranslationProvider()

    # Multiple calls — all should work without network
    results = [
        localize_product_name("石墨坩埚", "German", provider=mock),
        localize_product_name("硅胶密封圈", "French", provider=mock),
        localize_product_name("anti-static turnover box", "Vietnamese", provider=mock),
    ]

    for r in results:
        assert r.method != "fallback_original" or r.translation_missing
        assert r.product_original and r.product_localized

    # Verify specific translations
    assert results[0].product_localized == "Graphittiegel"
    assert results[1].product_localized == "joints d'étanchéité en silicone"
    assert results[2].product_localized == "thùng chứa chống tĩnh điện"


def test_product_localizer_does_not_require_product_in_builtin_glossary():
    """Any product can be translated via provider, even if not in glossary."""
    mock = MockTranslationProvider()

    # These products are NOT in the builtin glossary
    for product in ("石墨坩埚", "硅胶密封圈", "anti-static turnover box"):
        assert not _is_builtin_product(product), f"{product} should NOT be in builtin glossary"

    # But they still get translated via mock provider
    r1 = localize_product_name("石墨坩埚", "German", provider=mock)
    assert r1.method == "llm_structured_translation"
    assert not r1.translation_missing

    r2 = localize_product_name("硅胶密封圈", "French", provider=mock)
    assert r2.method == "llm_structured_translation"
    assert not r2.translation_missing


def test_default_provider_returns_none():
    """Default TranslationProvider returns None for any product."""
    provider = TranslationProvider()
    result = provider.translate_product_term("任何产品", "German")
    assert result is None


# ═══════════════════════════════════════════════════════════
# No None in output
# ═══════════════════════════════════════════════════════════

def test_no_none_when_translation_missing():
    """Even when translation fails, product_localized must not be None."""
    mock = MockTranslationProvider()
    result = localize_product_name("超小众冷门产品ABC", "German", provider=mock)

    assert result.product_localized is not None
    assert result.product_localized != "None"
    assert result.product_localized == "超小众冷门产品ABC"  # Fallback to original
    assert result.translation_missing is True


def test_no_none_in_any_field():
    """No field in the result should contain None as a string."""
    mock = MockTranslationProvider()
    result = localize_product_name("测试产品", "Spanish", provider=mock)

    d = result.to_dict()
    for key, value in d.items():
        if isinstance(value, str):
            assert "None" not in value, f"Field '{key}' contains 'None': {value}"


def test_assert_no_none_terms():
    """assert_no_none_terms catches literal 'None' in text."""
    assert assert_no_none_terms("Guía de proveedores de racores") is True
    assert assert_no_none_terms("None Supplier Guide") is False
    assert assert_no_none_terms("") is True
    assert assert_no_none_terms("Product details without none") is True


# ═══════════════════════════════════════════════════════════
# Quality check functions
# ═══════════════════════════════════════════════════════════

def test_product_localization_coverage():
    """product_localization_coverage scores presence of localized name."""
    text = "Guía de racores hidráulicos. Los racores hidráulicos B2B. Comprar racores hidráulicos."
    assert product_localization_coverage(text, "racores hidráulicos") == 1.0

    text_one = "Catálogo de racores hidráulicos para exportación."
    assert product_localization_coverage(text_one, "racores hidráulicos") == 0.5

    text_none = "Product catalog for export."
    assert product_localization_coverage(text_none, "racores hidráulicos") == 0.0


def test_validate_product_translation():
    """validate_product_translation rejects invalid translations."""
    assert validate_product_translation("液压接头", "racores hidráulicos", "Spanish") is True
    assert validate_product_translation("test", "", "Spanish") is False
    assert validate_product_translation("test", "None", "Spanish") is False
    assert validate_product_translation("test", "null", "Spanish") is False


def test_product_translation_missing_helper():
    """product_translation_missing correctly identifies missing translations."""
    r1 = ProductLocalizationResult(
        product_original="test", product_localized="test",
        target_language="German", method="builtin_glossary",
        confidence=0.95, translation_missing=False,
    )
    assert not product_translation_missing(r1)

    r2 = ProductLocalizationResult(
        product_original="test", product_localized="test",
        target_language="German", method="fallback_original",
        confidence=0.0, translation_missing=True,
    )
    assert product_translation_missing(r2)

    assert product_translation_missing(None) is True


# ═══════════════════════════════════════════════════════════
# Prompt builder
# ═══════════════════════════════════════════════════════════

def test_build_product_translation_prompt():
    """Prompt builder creates usable prompts without errors."""
    prompt = build_product_translation_prompt(
        "石墨坩埚", "German", industry="industrial materials", market="Germany"
    )
    assert "石墨坩埚" in prompt
    assert "German" in prompt
    assert "Graphittiegel" in prompt  # example in prompt
    assert "industrial materials" in prompt
    assert "Germany" in prompt


def test_parse_product_translation_response():
    """Parse valid and invalid provider responses."""
    # Valid JSON
    result = parse_product_translation_response(
        '{"product_localized": "Graphittiegel", "confidence": 0.88}'
    )
    assert result == {"product_localized": "Graphittiegel", "confidence": 0.88}

    # JSON with markdown fence
    result = parse_product_translation_response(
        '```json\n{"product_localized": "Test", "confidence": 0.9}\n```'
    )
    assert result == {"product_localized": "Test", "confidence": 0.9}

    # Invalid response
    assert parse_product_translation_response("") is None
    assert parse_product_translation_response("not json") is None


# ═══════════════════════════════════════════════════════════
# get_product_name_for_page integration
# ═══════════════════════════════════════════════════════════

def test_get_product_name_for_page_uses_localized():
    """get_product_name_for_page returns localized product when available."""
    intent = {
        "product": "液压接头",
        "product_localized": "racores hidráulicos",
        "language": "Spanish",
    }
    name = get_product_name_for_page(intent, "Spanish")
    assert name == "racores hidráulicos"


def test_get_product_name_for_page_falls_back_to_original():
    """When no localized product, fall back to product or display name."""
    intent = {"product": "特种钻头", "language": "German"}
    name = get_product_name_for_page(intent, "German")
    assert name == "特种钻头"  # Falls back (no provider, not in glossary)


def test_get_product_name_for_page_never_returns_none():
    """Even with empty intent, returns 'Product' not None."""
    assert get_product_name_for_page({}, "Spanish") == "Product"
    assert get_product_name_for_page(None, "English") == "Product"


# ═══════════════════════════════════════════════════════════
# Intent integration: product_localized stored in intent
# ═══════════════════════════════════════════════════════════

def test_intent_stores_product_localized():
    """merge_intent must compute and store product_localized."""
    from lib.intent_engine import empty_intent, merge_intent

    intent = merge_intent(empty_intent(), "做一个液压接头西班牙语B2B出口站")
    assert intent["product"] == "液压接头"
    assert intent["product_localized"] == "racores hidráulicos"
    assert intent.get("translation_missing") is False


def test_intent_product_localized_for_open_vocab_with_mock():
    """merge_intent with open vocab should also work (using builtin or mock)."""
    from lib.intent_engine import empty_intent, merge_intent

    # Cold chain box is in builtin glossary for Indonesian
    intent = merge_intent(empty_intent(), "做一个冷链保温箱印尼语B2B出口站")
    assert intent["product"] == "冷链保温箱"
    assert intent["language"] == "Indonesian"
    assert intent["product_localized"] == "kotak insulasi rantai dingin"
    assert intent.get("translation_missing") is False
