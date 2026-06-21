# -*- coding: utf-8 -*-
"""tests/test_language_normalizer.py · Phase 9.3.9: Language Normalizer Tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.language_normalizer import normalize, extract_from_phrase


def test_japanese_variants():
    assert normalize("日语")["language"] == "Japanese"
    assert normalize("日文")["language"] == "Japanese"
    assert normalize("Japanese")["language"] == "Japanese"
    assert normalize("ja")["language"] == "Japanese"
    assert normalize("日本語")["language"] == "Japanese"


def test_german_variants():
    assert normalize("德语")["language"] == "German"
    assert normalize("德文")["language"] == "German"
    assert normalize("German")["language"] == "German"
    assert normalize("Deutsch")["language"] == "German"
    assert normalize("de")["language"] == "German"


def test_french_variants():
    assert normalize("法语")["language"] == "French"
    assert normalize("French")["language"] == "French"
    assert normalize("Français")["language"] == "French"
    assert normalize("fr")["language"] == "French"


def test_spanish_variants():
    assert normalize("西班牙语")["language"] == "Spanish"
    assert normalize("西语")["language"] == "Spanish"
    assert normalize("Spanish")["language"] == "Spanish"
    assert normalize("Español")["language"] == "Spanish"


def test_arabic_variants():
    assert normalize("阿拉伯语")["language"] == "Arabic"
    assert normalize("Arabic")["language"] == "Arabic"
    assert normalize("العربية")["language"] == "Arabic"


def test_vietnamese_variants():
    assert normalize("越南语")["language"] == "Vietnamese"
    assert normalize("Vietnamese")["language"] == "Vietnamese"
    assert normalize("vi")["language"] == "Vietnamese"


def test_thai_variants():
    assert normalize("泰语")["language"] == "Thai"
    assert normalize("Thai")["language"] == "Thai"


def test_indonesian_variants():
    assert normalize("印尼语")["language"] == "Indonesian"
    assert normalize("Indonesian")["language"] == "Indonesian"


def test_portuguese_variants():
    assert normalize("葡萄牙语")["language"] == "Portuguese"
    assert normalize("Portuguese")["language"] == "Portuguese"


def test_chinese_variants():
    assert normalize("中文")["language"] == "Chinese"
    assert normalize("Chinese")["language"] == "Chinese"
    assert normalize("简体中文")["language"] == "Chinese"


def test_unknown_language_defaults_english_with_low_confidence():
    r = normalize("xyz-unknown-language")
    assert r["language"] == "English"
    assert r.get("language_confidence") == "defaulted"


def test_user_can_override_default_language():
    # First normalize shows defaulted
    r1 = normalize("xyz")
    assert r1.get("language_confidence") == "defaulted"
    # Then user says "日语" — must override
    r2 = normalize("日语")
    assert r2["language"] == "Japanese"
    assert "language_confidence" not in r2


def test_extract_from_phrase_chinese():
    r = extract_from_phrase("要日语的")
    assert r is not None
    assert r["language"] == "Japanese"

    r = extract_from_phrase("做日语版")
    assert r is not None
    assert r["language"] == "Japanese"

    r = extract_from_phrase("页面用日语")
    assert r is not None
    assert r["language"] == "Japanese"


def test_extract_from_phrase_english():
    r = extract_from_phrase("in French")
    assert r is not None
    assert r["language"] == "French"

    r = extract_from_phrase("target language: Japanese")
    assert r is not None
    assert r["language"] == "Japanese"


def test_locale_and_script_output():
    r = normalize("日语")
    assert r["locale"] == "ja-JP"
    assert r["script"] == "Jpan"

    r = normalize("Russian")
    assert r["locale"] == "ru-RU"
    assert r["script"] == "Cyrl"

    r = normalize("Arabic")
    assert r["script"] == "Arab"
