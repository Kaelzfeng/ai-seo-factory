# -*- coding: utf-8 -*-
"""Phase 9.4.1 multilingual localization behavior contracts."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def _localization():
    assert importlib.util.find_spec("lib.localization") is not None, "shared localization layer is missing"
    import lib.localization as localization
    return localization


def _intent(message: str) -> dict:
    from lib.intent_engine import empty_intent, merge_intent
    return merge_intent(empty_intent(), message)


def _page(product: str, language: str, market=None, page_type="supplier_guide") -> dict:
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    brief = build_industry_brief({
        "product": product,
        "language": language,
        "market": market,
        "audience": "B2B buyers and distributors",
    })
    return write_page_content({"type": page_type}, brief)


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


def test_language_normalizer_supports_18_languages():
    loc = _localization()
    variants = {
        "English": "en-US", "Japanese": "ja-JP", "Korean": "ko",
        "German": "de", "French": "fr", "Spanish": "es",
        "Portuguese": "pt", "Italian": "it", "Russian": "ru",
        "Arabic": "ar", "Vietnamese": "vi", "Thai": "th",
        "Indonesian": "id", "Malay": "ms", "Dutch": "nl",
        "Turkish": "tr", "Polish": "pl", "Chinese Simplified": "zh-CN",
        "Chinese Traditional": "zh-TW",
    }
    assert len({loc.normalize_language(value) for value in variants.values()}) == 19


@pytest.mark.parametrize("value", ["日语", "日文", "Japanese", "日本語", "ja", "ja-JP"])
def test_japanese_language_variants(value):
    assert _localization().normalize_language(value) == "Japanese"


@pytest.mark.parametrize("value", ["西班牙语", "西语", "Spanish", "Español", "es"])
def test_spanish_language_variants(value):
    assert _localization().normalize_language(value) == "Spanish"


@pytest.mark.parametrize("value", ["德语", "German", "Deutsch", "de"])
def test_german_language_variants(value):
    assert _localization().normalize_language(value) == "German"


@pytest.mark.parametrize("value", ["法语", "French", "Français", "fr"])
def test_french_language_variants(value):
    assert _localization().normalize_language(value) == "French"


@pytest.mark.parametrize("value", ["葡萄牙语", "Portuguese", "Português", "pt"])
def test_portuguese_language_variants(value):
    assert _localization().normalize_language(value) == "Portuguese"


@pytest.mark.parametrize("value", ["阿拉伯语", "Arabic", "العربية", "ar"])
def test_arabic_language_variants(value):
    assert _localization().normalize_language(value) == "Arabic"


@pytest.mark.parametrize("value", ["越南语", "Vietnamese", "Tiếng Việt", "vi"])
def test_vietnamese_language_variants(value):
    assert _localization().normalize_language(value) == "Vietnamese"


@pytest.mark.parametrize("value", ["泰语", "Thai", "ภาษาไทย", "th"])
def test_thai_language_variants(value):
    assert _localization().normalize_language(value) == "Thai"


@pytest.mark.parametrize("value", ["印尼语", "Indonesian", "Bahasa Indonesia", "id"])
def test_indonesian_language_variants(value):
    assert _localization().normalize_language(value) == "Indonesian"


def test_chinese_simplified_and_traditional_variants():
    loc = _localization()
    from lib.language_normalizer import normalize
    for value in ("中文", "Chinese", "简体中文", "zh", "zh-CN"):
        assert loc.normalize_language(value) == "Chinese Simplified"
    for value in ("繁体中文", "繁體中文", "zh-TW"):
        assert loc.normalize_language(value) == "Chinese Traditional"
    assert normalize("简体中文")["locale"] == "zh-CN"
    assert normalize("繁体中文")["locale"] == "zh-TW"
    assert normalize("繁體中文")["script"] == "Hant"
    traditional = _intent("做一个液压接头繁体中文B2B出口站")
    assert traditional["language"] == "Chinese Traditional"
    assert traditional["locale"] == "zh-TW"


def test_spanish_language_not_confused_with_spain_market():
    intent = _intent("做一个液压接头西班牙语B2B出口站")
    assert intent["language"] == "Spanish"
    assert intent["locale"] == "es-ES"
    assert intent["market"] is None


def test_spain_market_not_confused_with_spanish_language():
    intent = _intent("做一个液压接头西班牙市场B2B出口站，英文")
    assert intent["language"] == "English"
    assert _localization().normalize_market(intent["market"]) == "Spain"


def test_japanese_language_not_confused_with_japan_market():
    intent = _intent("做一个铁管日语出口站")
    assert intent["language"] == "Japanese"
    assert intent["locale"] == "ja-JP"
    assert intent["market"] is None


def test_japan_market_not_confused_with_japanese_language():
    intent = _intent("做一个铁管英文出口站，日本市场")
    assert intent["language"] == "English"
    assert _localization().normalize_market(intent["market"]) == "Japan"


def test_german_language_not_confused_with_germany_market():
    intent = _intent("industrial belt German website")
    assert intent["language"] == "German"
    assert intent["market"] is None


def test_germany_market_not_confused_with_german_language():
    intent = _intent("industrial belt English website for Germany distributors")
    assert intent["language"] == "English"
    assert _localization().normalize_market(intent["market"]) == "Germany"


def test_french_language_not_confused_with_france_market():
    intent = _intent("generate SEO pages for hose clamps in French")
    assert intent["language"] == "French"
    assert intent["market"] is None


def test_france_market_not_confused_with_french_language():
    intent = _intent("generate SEO pages for hose clamps in English for France distributors")
    assert intent["language"] == "English"
    assert _localization().normalize_market(intent["market"]) == "France"


def test_product_display_name_strips_language_suffix():
    from lib.intent_engine import get_product_display_name
    intent = _intent("做一个液压接头西班牙语B2B出口站")
    assert get_product_display_name(intent) == "液压接头"


def test_product_display_name_strips_market_suffix():
    from lib.intent_engine import get_product_display_name
    intent = _intent("做一个液压接头西班牙市场B2B出口站，英文")
    assert get_product_display_name(intent) == "液压接头"


def test_product_display_name_strips_site_type_suffix():
    loc = _localization()
    assert loc.clean_product_display_name("industrial belt German website for Germany distributors") == "industrial belt"
    assert loc.clean_product_display_name("鉄管日本市場向け日語サイト") == "鉄管"


def test_product_display_name_never_contains_none():
    from lib.intent_engine import get_product_display_name
    assert get_product_display_name({"product": None, "industry": None}) == "Product"
    assert "none" not in get_product_display_name({"product": "None"}).casefold()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("铁管日语出口站，日本市场", "铁管"),
        ("液压接头西班牙语B2B出口站", "液压接头"),
        ("陶瓷杯法语B2B网站，面向欧洲礼品采购商", "陶瓷杯"),
        ("工业皮带德语外贸站，面向德国工厂采购商", "工业皮带"),
        ("宠物梳葡萄牙语站，面向巴西宠物店", "宠物梳"),
        ("cold chain insulated box Indonesian B2B export website", "cold chain insulated box"),
    ],
)
def test_product_display_name_cleaned_across_industries(raw, expected):
    assert _localization().clean_product_display_name(raw) == expected


@pytest.mark.parametrize(
    "language,product,required",
    [
        ("Spanish", "línea de racores hidráulicos", ("proveedores", "compradores", "especificaciones", "cotización")),
        ("Japanese", "鉄管", ("仕様", "梱包", "輸出", "見積", "バイヤー")),
        ("German", "Industriegürtel", ("Käufer", "Spezifikationen", "Verpackung", "Angebot")),
        ("French", "raccords hydrauliques", ("acheteurs", "spécifications", "emballage", "devis")),
        ("Portuguese", "caneca de cerâmica", ("compradores", "especificações", "embalagem", "cotação")),
        ("Arabic", "وصلات هيدروليكية", ("المواصفات", "التغليف", "التصدير", "الجودة")),
        ("Vietnamese", "khớp nối thủy lực", ("thông số", "đóng gói", "xuất khẩu", "chất lượng")),
        ("Thai", "ข้อต่อไฮดรอลิก", ("ข้อมูลจำเพาะ", "บรรจุภัณฑ์", "ส่งออก", "คุณภาพ")),
        ("Indonesian", "fitting hidrolik", ("spesifikasi", "kemasan", "ekspor", "kualitas")),
        ("Chinese Simplified", "液压接头", ("规格", "包装", "出口", "报价", "质量")),
        ("Chinese Traditional", "液壓接頭", ("規格", "包裝", "出口", "報價", "品質")),
    ],
)
def test_localized_page_body_uses_target_language(language, product, required):
    loc = _localization()
    page = _page(product, language, market="Spain" if language == "Spanish" else None)
    text = page["title"] + " " + page["html"]
    assert all(term.casefold() in text.casefold() for term in required)
    assert loc.language_coverage_score(text, language) >= 0.55


def test_spanish_page_uses_spanish_titles_and_body():
    test_localized_page_body_uses_target_language("Spanish", "racores hidráulicos", ("proveedores", "compradores", "especificaciones", "cotización"))


def test_japanese_page_uses_japanese_titles_and_body():
    test_localized_page_body_uses_target_language("Japanese", "鉄管", ("仕様", "梱包", "輸出", "見積", "バイヤー"))


def test_german_page_uses_german_titles_and_body():
    test_localized_page_body_uses_target_language("German", "Industriegürtel", ("Käufer", "Spezifikationen", "Verpackung", "Angebot"))


def test_french_page_uses_french_titles_and_body():
    test_localized_page_body_uses_target_language("French", "raccord hydraulique", ("acheteurs", "spécifications", "emballage", "devis"))


def test_portuguese_page_uses_portuguese_titles_and_body():
    test_localized_page_body_uses_target_language("Portuguese", "caneca de cerâmica", ("compradores", "especificações", "embalagem", "cotação"))


def test_arabic_page_uses_arabic_terms():
    test_localized_page_body_uses_target_language("Arabic", "وصلات", ("المواصفات", "التغليف", "التصدير", "الجودة"))


def test_vietnamese_page_uses_vietnamese_terms():
    test_localized_page_body_uses_target_language("Vietnamese", "khớp nối", ("thông số", "đóng gói", "xuất khẩu", "chất lượng"))


def test_thai_page_uses_thai_terms():
    test_localized_page_body_uses_target_language("Thai", "ข้อต่อ", ("ข้อมูลจำเพาะ", "บรรจุภัณฑ์", "ส่งออก", "คุณภาพ"))


def test_indonesian_page_uses_indonesian_terms():
    test_localized_page_body_uses_target_language("Indonesian", "fitting", ("spesifikasi", "kemasan", "ekspor", "kualitas"))


def test_chinese_page_uses_chinese_terms():
    test_localized_page_body_uses_target_language("Chinese Simplified", "液压接头", ("规格", "包装", "出口", "报价", "质量"))


def test_market_can_be_used_in_copy_without_polluting_product_name():
    from lib.intent_engine import get_product_display_name
    intent = _intent("做一个液压接头西班牙市场B2B出口站，英文")
    product = get_product_display_name(intent)
    page = _page(product, intent["language"], intent["market"], "export")
    assert product == "液压接头"
    assert "Spain" in page["html"] or "Spanish market" in page["html"]
    assert "西班牙" not in page["title"]


def _localized_scenario(message: str, required_terms: tuple[str, ...]):
    """Phase 9.4.1: Uses product_localized from brief (not raw original)."""
    from lib.intent_engine import get_product_display_name
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    intent = _intent(message)
    # Phase 9.4.1: build_industry_brief now uses product_localized
    brief = build_industry_brief(intent)
    page = write_page_content({"type": "supplier_guide"}, brief)
    text = (page["title"] + " " + page["html"]).casefold()
    # Verify the product used in content (localized) appears in text
    assert brief.product.casefold() in text, f"Product '{brief.product}' not found in text"
    assert all(term.casefold() in text for term in required_terms)
    assert "none" not in text
    return intent, brief, page


def test_multilingual_pipe_japanese_market():
    intent, brief, _ = _localized_scenario(
        "做一个铁管日语出口站，日本市场",
        ("外径", "肉厚", "長さ", "亜鉛メッキ", "梱包", "MOQ", "輸出書類"),
    )
    assert intent["product"] == "铁管"
    assert intent["language"] == "Japanese"
    assert _localization().normalize_market(brief.market) == "Japan"


def test_multilingual_hydraulic_spanish():
    intent, _, _ = _localized_scenario(
        "做一个液压接头西班牙语B2B出口站",
        ("BSP", "NPT", "JIC", "DIN", "presión", "sellado", "compradores", "especificaciones"),
    )
    assert intent["product"] == "液压接头"
    assert intent["language"] == "Spanish"
    assert intent["market"] is None


def test_multilingual_ceramic_french():
    intent, brief, _ = _localized_scenario(
        "做一个陶瓷杯法语B2B网站，面向欧洲礼品采购商",
        ("capacité", "glaçure", "emballage", "logo personnalisé", "sécurité alimentaire", "acheteurs"),
    )
    assert intent["product"] == "陶瓷杯"
    assert intent["audience"] == "gift buyers"
    assert _localization().normalize_market(brief.market) == "Europe"


def test_multilingual_industrial_belt_german():
    intent, brief, _ = _localized_scenario(
        "做一个工业皮带德语外贸站，面向德国工厂采购商",
        ("Spezifikationen", "Material", "Verschleißfestigkeit", "Zugfestigkeit", "Verpackung", "Lieferzeit"),
    )
    assert intent["product"] == "工业皮带"
    assert intent["audience"] == "factory buyers"
    assert _localization().normalize_market(brief.market) == "Germany"


def test_multilingual_pet_product_portuguese():
    intent, brief, _ = _localized_scenario(
        "做一个宠物梳葡萄牙语站，面向巴西宠物店",
        ("segurança do material", "tamanho do animal", "durabilidade", "limpeza", "embalagem", "compradores"),
    )
    assert intent["product"] == "宠物梳"
    assert intent["audience"] == "pet shops"
    assert _localization().normalize_market(brief.market) == "Brazil"


def test_multilingual_packaging_display_arabic():
    intent, brief, _ = _localized_scenario(
        "create an Arabic B2B website for acrylic display stands, target Middle East distributors",
        ("المواصفات", "التغليف", "الموزعين", "عرض سعر", "الجودة", "acrylic", "thickness", "retail display"),
    )
    assert "acrylic display" in intent["product"].casefold()
    assert intent["audience"] == "Distributors"
    assert _localization().normalize_market(brief.market) == "Middle East"


def test_multilingual_textile_vietnamese():
    intent, brief, _ = _localized_scenario(
        "generate a Vietnamese wholesale website for custom T-shirts, target Southeast Asian brand buyers",
        ("thông số", "chất liệu vải", "kích cỡ", "in logo", "đóng gói", "báo giá"),
    )
    assert "t-shirt" in intent["product"].casefold()
    assert intent["audience"] == "brand buyers"
    assert _localization().normalize_market(brief.market) == "Southeast Asia"


def test_multilingual_unknown_product_indonesian():
    """冷链保温箱 is in builtin glossary → localized Indonesian used in page."""
    intent, brief, page = _localized_scenario(
        "做一个冷链保温箱印尼语B2B出口站",
        ("spesifikasi", "kemasan", "ekspor", "pembeli", "penawaran", "kualitas"),
    )
    assert intent["product"] == "冷链保温箱"
    # Phase 9.4.1: product is localized — page uses Indonesian, not Chinese
    assert "kotak insulasi" in page["html"].lower() or "cold chain" in page["html"].lower()
    # No None anywhere
    assert "None" not in page["title"]
    assert "none" not in page["html"].lower()


def test_language_market_disambiguation_across_industries():
    cases = (
        ("液压接头西班牙语B2B出口站", "Spanish", None),
        ("做一个铁管日语出口站，日本市场", "Japanese", "Japan"),
        ("工业皮带德语外贸站，面向德国工厂采购商", "German", "Germany"),
        ("陶瓷杯法语B2B网站，面向法国采购商", "French", "France"),
    )
    for message, language, market in cases:
        intent = _intent(message)
        assert intent["language"] == language
        assert _localization().normalize_market(intent["market"]) == market


def test_industry_terms_survive_localization():
    scenarios = (
        ("hydraulic fitting", "Spanish", ("BSP", "NPT", "JIC", "DIN")),
        ("steel pipe", "Japanese", ("ASTM", "outer diameter", "wall thickness")),
        ("ceramic mug", "French", ("food contact safety", "drop test")),
    )
    for product, language, terms in scenarios:
        page = _page(product, language)
        assert all(term.casefold() in page["html"].casefold() for term in terms)


def test_localized_content_not_same_template_across_industries():
    pipe = _page("steel pipe", "Spanish")["html"]
    ceramic = _page("ceramic mug", "Spanish")["html"]
    pet = _page("pet grooming brush", "Spanish")["html"]
    assert len({pipe, ceramic, pet}) == 3
    assert "outer diameter" in pipe
    assert "food contact safety" in ceramic
    assert "pet size" in pet


def test_no_none_in_localized_titles():
    loc = _localization()
    for language in loc.supported_languages():
        title = loc.localize_page_title("supplier_guide", None, language, market=None)
        assert "none" not in title.casefold()
        assert title.strip()


def test_localized_pages_are_not_english_boilerplate_only():
    loc = _localization()
    for language in ("Japanese", "Spanish", "German", "French", "Portuguese", "Arabic", "Vietnamese", "Thai", "Indonesian", "Chinese Simplified"):
        page = _page("industrial product", language)
        assert loc.language_coverage_score(page["html"], language) >= 0.55
        assert "is evaluated by b2b buyers" not in page["html"].casefold()


def test_all_supported_languages_have_titles_sections_cta_and_body_copy():
    loc = _localization()
    assert len(loc.supported_languages()) == 19
    for language in loc.supported_languages():
        page = _page("industrial product", language)
        assert page["title"]
        assert "<h2>" in page["html"]
        assert page["cta"] in page["html"]
        assert loc.language_coverage_score(page["html"], language) >= 0.55


def test_low_language_coverage_reinforces_normal_llm_content():
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import reinforce_page_content

    brief = build_industry_brief({"product": "hydraulic fitting", "language": "Spanish"})
    english_only = {
        "title": "Hydraulic fitting selection",
        "html": (
            "<h1>Hydraulic fitting selection</h1><p>Compare thread standard, pressure rating, "
            "sealing type, BSP, NPT, JIC, DIN, leakage risk and material grade.</p>"
        ),
    }
    result = reinforce_page_content(english_only, {"type": "supplier_guide"}, brief)
    assert result["html"] != english_only["html"]
    assert _localization().language_coverage_score(result["html"], "Spanish") >= 0.55


# ═══════════════════════════════════════════════════════════
# Phase 9.4.1: Open-vocabulary multilingual tests
# ═══════════════════════════════════════════════════════════

def test_multilingual_open_vocab_graphite_crucible_german():
    """石墨坩埚 not in builtin glossary — translated via mock provider."""
    from lib.product_localizer import MockTranslationProvider, localize_product_name
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    mock = MockTranslationProvider()
    loc_result = localize_product_name("石墨坩埚", "German", provider=mock)

    brief = build_industry_brief({
        "product": "石墨坩埚",
        "product_localized": loc_result.product_localized,
        "language": "German",
        "market": "Germany",
        "audience": "B2B buyers and distributors",
    })
    page = write_page_content({"type": "supplier_guide"}, brief)

    text = (page["title"] + " " + page["html"])
    # Must use localized product
    assert "Graphittiegel" in text
    # Must not contain Chinese original in visible text
    assert "石墨坩埚" not in page["title"]
    # Must contain German business terms
    assert any(term in text for term in ("Spezifikationen", "Lieferzeit", "Verpackung", "Qualität"))
    assert "None" not in text
    assert "none" not in text.lower()


def test_multilingual_open_vocab_silicone_seal_french():
    """硅胶密封圈 not in builtin glossary — translated via mock provider."""
    from lib.product_localizer import MockTranslationProvider, localize_product_name
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    mock = MockTranslationProvider()
    loc_result = localize_product_name("硅胶密封圈", "French", provider=mock)

    brief = build_industry_brief({
        "product": "硅胶密封圈",
        "product_localized": loc_result.product_localized,
        "language": "French",
        "market": "France",
        "audience": "distributeurs",
    })
    page = write_page_content({"type": "supplier_guide"}, brief)

    text = (page["title"] + " " + page["html"])
    assert "joints d'étanchéité en silicone" in text
    assert "硅胶密封圈" not in page["title"]
    assert any(term in text for term in ("spécifications", "emballage", "devis", "qualité"))
    assert "None" not in text


def test_multilingual_open_vocab_anti_static_turnover_box_vietnamese():
    """anti-static turnover box translated via mock provider to Vietnamese."""
    from lib.product_localizer import MockTranslationProvider, localize_product_name
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    mock = MockTranslationProvider()
    loc_result = localize_product_name(
        "anti-static turnover box", "Vietnamese", provider=mock
    )

    brief = build_industry_brief({
        "product": "anti-static turnover box",
        "product_localized": loc_result.product_localized,
        "language": "Vietnamese",
        "market": "Vietnam",
        "audience": "B2B buyers",
    })
    page = write_page_content({"type": "supplier_guide"}, brief)

    text = (page["title"] + " " + page["html"])
    assert "thùng chứa chống tĩnh điện" in text
    assert "None" not in text


def test_multilingual_unknown_product_translation_missing_but_no_none():
    """When translation fails, page still renders without None."""
    from lib.industry_brief import build_industry_brief
    from lib.page_content_writer import write_page_content

    # A product not in any glossary and no provider available
    brief = build_industry_brief({
        "product": "特种合金微型钻头",
        "language": "German",
        "market": "Germany",
        "audience": "factory buyers",
    })
    page = write_page_content({"type": "supplier_guide"}, brief)

    assert "None" not in page["title"]
    assert "none" not in page["html"].lower()
    assert page["title"].strip()


def test_output_src_not_modified():
    before = _tree_digest(ROOT / "output_src")
    _page("hydraulic fitting", "Spanish", "Spain")
    assert _tree_digest(ROOT / "output_src") == before


def test_static_not_modified():
    before = _tree_digest(ROOT / "static")
    _page("hydraulic fitting", "Japanese", "Japan")
    assert _tree_digest(ROOT / "static") == before
