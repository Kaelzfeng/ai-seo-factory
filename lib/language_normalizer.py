# -*- coding: utf-8 -*-
"""lib/language_normalizer.py · Phase 9.3.9: Multilingual Language Detection

Supports 18 languages via Chinese name, English name, native name,
ISO code, and phrase patterns ("要日语的", "in French", etc.).

Returns: {"language": "English", "locale": "en-US", "script": "Latn"}
For unrecognized: {"language": "English", "locale": "en-US", "script": "Latn",
                   "language_confidence": "defaulted"}
"""

import re

# Each entry: (english_name, (chinese_names...), (native_names...), locale, script)
_LANGUAGES = [
    ("English",    ("英语", "英文", "en", "en-US", "en-GB"),          ("English",),               "en-US", "Latn"),
    ("Japanese",   ("日语", "日文", "ja", "ja-JP", "日本語"),          ("日本語", "にほんご"),       "ja-JP", "Jpan"),
    ("Korean",     ("韩语", "韩文", "ko", "ko-KR", "한국어", "한글"),  ("한국어", "한글"),           "ko-KR", "Kore"),
    ("German",     ("德语", "德文", "de", "de-DE"),                   ("Deutsch",),                "de-DE", "Latn"),
    ("French",     ("法语", "法文", "fr", "fr-FR"),                   ("Français",),               "fr-FR", "Latn"),
    ("Spanish",    ("西班牙语", "西语", "es", "es-ES", "es-MX"),      ("Español",),                "es-ES", "Latn"),
    ("Portuguese", ("葡萄牙语", "葡语", "pt", "pt-BR", "pt-PT"),      ("Português",),              "pt-BR", "Latn"),
    ("Italian",    ("意大利语", "it", "it-IT"),                        ("Italiano",),               "it-IT", "Latn"),
    ("Russian",    ("俄语", "俄文", "ru", "ru-RU"),                    ("Русский",),                "ru-RU", "Cyrl"),
    ("Arabic",     ("阿拉伯语", "ar", "ar-SA"),                        ("العربية",),                "ar-SA", "Arab"),
    ("Vietnamese", ("越南语", "vi", "vi-VN"),                          ("Tiếng Việt",),             "vi-VN", "Latn"),
    ("Thai",       ("泰语", "th", "th-TH"),                            ("ภาษาไทย",),                "th-TH", "Thai"),
    ("Indonesian", ("印尼语", "印度尼西亚语", "id", "id-ID"),          ("Bahasa Indonesia",),       "id-ID", "Latn"),
    ("Malay",      ("马来语", "ms", "ms-MY"),                          ("Bahasa Melayu",),          "ms-MY", "Latn"),
    ("Dutch",      ("荷兰语", "nl", "nl-NL"),                          ("Nederlands",),             "nl-NL", "Latn"),
    ("Turkish",    ("土耳其语", "tr", "tr-TR"),                        ("Türkçe",),                 "tr-TR", "Latn"),
    ("Polish",     ("波兰语", "pl", "pl-PL"),                          ("Polski",),                 "pl-PL", "Latn"),
    ("Chinese",    ("中文", "汉语", "简体中文", "繁体中文", "zh", "zh-CN", "zh-TW"),
                   ("中文", "简体中文", "繁體中文"),                    "zh-CN", "Hans"),
]


def normalize(text):
    """Normalize any language expression to a standard dict.

    Args:
        text: A language keyword like "日语", "Japanese", "ja", "Deutsch", "in French"

    Returns:
        {"language": "Japanese", "locale": "ja-JP", "script": "Jpan"}
        or with "language_confidence": "defaulted" if unrecognized.
    """
    t = (text or "").strip()
    if not t:
        return {"language": "English", "locale": "en-US", "script": "Latn",
                "language_confidence": "defaulted"}

    t_lower = t.lower()

    # Keep the long-standing language="Chinese" value for compatibility,
    # while locale/script preserve the writing-system distinction required by
    # the localization writer.
    chinese_key = t_lower.replace("_", "-")
    if any(alias in chinese_key for alias in (
        "繁体中文", "繁體中文", "traditional chinese", "chinese traditional", "zh-tw", "zh-hant",
    )):
        return {"language": "Chinese", "locale": "zh-TW", "script": "Hant"}
    if any(alias in chinese_key for alias in (
        "简体中文", "簡體中文", "simplified chinese", "chinese simplified", "zh-cn", "zh-hans",
    )):
        return {"language": "Chinese", "locale": "zh-CN", "script": "Hans"}

    for lang_name, cn_names, native_names, locale, script in _LANGUAGES:
        # Check English name first (exact match, case-insensitive)
        if lang_name.lower() == t_lower:
            return {"language": lang_name, "locale": locale, "script": script}
        # Check Chinese names (exact match for multi-char, or word-boundary for short codes)
        for cn in cn_names:
            if cn == t or (len(cn) >= 3 and cn in t):
                return {"language": lang_name, "locale": locale, "script": script}
            # Short codes (2 chars): only match as whole word
            if len(cn) <= 2 and (t == cn or t_lower == cn.lower()):
                return {"language": lang_name, "locale": locale, "script": script}
        # Check native names (exact or as distinct substring)
        for nat in native_names:
            if nat in t and len(nat) >= 3:
                return {"language": lang_name, "locale": locale, "script": script}

    return {"language": "English", "locale": "en-US", "script": "Latn",
            "language_confidence": "defaulted"}


def extract_from_phrase(text):
    """Extract language from phrase patterns like '要日语的', 'in French', etc.

    Returns (language_name, locale, script) or None if no language pattern found.
    """
    t = text.strip()
    if not t:
        return None

    # Chinese phrase patterns — check for language keywords adjacent to common markers
    # Pattern: <marker> + <language_keyword>
    cn_markers = [
        (r"要(.+?)的", 1),           # 要日语的 → 日语
        (r"做(.+?)版", 1),          # 做日语版 → 日语
        (r"写成(.+)", 1),           # 写成德语 → 德语
        (r"用(.+?)(?:语|文)", 1),   # 用日语 → 日语
        (r"目标语言[是为：:\s]*(.+)", 1),  # 目标语言是法语 → 法语
        (r"语言[是为：:\s]*(.+)", 1),     # 语言是日语 → 日语
    ]
    for pat_str, grp in cn_markers:
        m = re.search(pat_str, t)
        if m:
            kw = m.group(grp).strip()
            # Try normalize directly; also try appending 语 if needed
            result = normalize(kw)
            if result.get("language_confidence") == "defaulted" and len(kw) <= 3:
                result = normalize(kw + "语")  # append 语
            if result.get("language_confidence") != "defaulted":
                return result

    # Check for language keyword + 站 (site) pattern: 西语站, 日语站, 英文站
    m = re.search(r"(\S+?)(?:语|文)?站\b", t)
    if m:
        kw = m.group(1).strip()
        if len(kw) <= 3:
            kw = kw + "语"
        result = normalize(kw)
        if result.get("language_confidence") != "defaulted":
            return result

    # English phrase patterns: "in French", "write it in Spanish", "target language: Japanese"
    en_phrase_patterns = [
        r"in\s+(\w+)",                              # in French, in Japanese
        r"(?:write|written)\s+(?:it\s+)?in\s+(\w+)", # write it in Spanish
        r"target\s+language\s*[:=]?\s*(\w+)",        # target language: Japanese
        r"language\s*[:=]?\s*(\w+)",                 # language: German
    ]
    for pat in en_phrase_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            kw = m.group(1).strip()
            result = normalize(kw)
            if result.get("language_confidence") != "defaulted":
                return result

    # Direct language short codes: ja, en, de, fr, es, etc.
    short_code_pattern = r'\b(ja|en|de|fr|es|pt|it|ru|ar|vi|th|id|ms|nl|tr|pl|ko|zh)(?:[-_]\w+)?\b'
    m = re.search(short_code_pattern, t, re.IGNORECASE)
    if m:
        result = normalize(m.group(1))
        if result.get("language_confidence") != "defaulted":
            return result

    return None
