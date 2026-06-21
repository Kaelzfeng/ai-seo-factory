# -*- coding: utf-8 -*-
"""lib/product_localizer.py · Phase 9.4.1: Open Product Localization Engine

Provides open-vocabulary product name translation with:
- Small builtin glossary (high-frequency fallback only, NOT exhaustive)
- Provider interface for structured translation (mockable for tests)
- Quality checks: source-language leak detection, missing-translation marking
- product_original always preserved for audit

Design principle:
    The builtin glossary is a FALLBACK, not a gate. Any product can be
    translated via the provider — even products never seen before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# Result structure
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProductLocalizationResult:
    """Structured result from product name localization."""
    product_original: str
    product_localized: str
    target_language: str
    locale: str = ""
    method: str = "fallback_original"  # builtin_glossary | llm_structured_translation | fallback_original
    confidence: float = 0.0
    translation_missing: bool = False

    def to_dict(self) -> dict:
        return {
            "product_original": self.product_original,
            "product_localized": self.product_localized,
            "target_language": self.target_language,
            "locale": self.locale,
            "method": self.method,
            "confidence": self.confidence,
            "translation_missing": self.translation_missing,
        }


# ═══════════════════════════════════════════════════════════════════
# Small builtin glossary — HIGH-FREQUENCY FALLBACK ONLY
#
# This is NOT meant to cover all industries. It handles the most
# common products so the system works fast for frequent queries.
# Anything not in this glossary goes through the provider.
# ═══════════════════════════════════════════════════════════════════

_BUILTIN_GLOSSARY = {
    # Chinese → {language: localized}
    "液压接头": {
        "Spanish": "racores hidráulicos",
        "French": "raccords hydrauliques",
        "German": "Hydraulikanschlüsse",
        "Japanese": "油圧継手",
        "Korean": "유압 피팅",
        "Portuguese": "conexões hidráulicas",
        "Arabic": "وصلات هيدروليكية",
        "Vietnamese": "khớp nối thủy lực",
        "Thai": "ข้อต่อไฮดรอลิก",
        "Indonesian": "fitting hidrolik",
        "English": "hydraulic fittings",
    },
    "铁管": {
        "Japanese": "鉄管",
        "Spanish": "tubos de acero",
        "French": "tubes en acier",
        "German": "Stahlrohre",
        "Korean": "강관",
        "English": "steel pipes",
        "Portuguese": "tubos de aço",
        "Arabic": "أنابيب فولاذية",
        "Vietnamese": "ống thép",
        "Thai": "ท่อเหล็ก",
        "Indonesian": "pipa baja",
    },
    "陶瓷杯": {
        "Spanish": "tazas de cerámica",
        "French": "tasses en céramique",
        "German": "Keramiktassen",
        "Japanese": "セラミックカップ",
        "Korean": "세라믹 컵",
        "English": "ceramic mugs",
        "Portuguese": "canecas de cerâmica",
        "Arabic": "أكواب سيراميك",
        "Vietnamese": "cốc sứ",
        "Thai": "แก้วเซรามิก",
        "Indonesian": "cangkir keramik",
    },
    "工业皮带": {
        "German": "Industriegurte",
        "Japanese": "工業用ベルト",
        "Spanish": "correas industriales",
        "French": "courroies industrielles",
        "Korean": "산업용 벨트",
        "English": "industrial belts",
        "Portuguese": "correias industriais",
        "Arabic": "سيور صناعية",
        "Vietnamese": "dây đai công nghiệp",
        "Thai": "สายพานอุตสาหกรรม",
        "Indonesian": "sabuk industri",
    },
    "宠物梳": {
        "Portuguese": "escova para animais de estimação",
        "Spanish": "cepillo para mascotas",
        "French": "brosse pour animaux",
        "German": "Haustierbürste",
        "Japanese": "ペット用ブラシ",
        "Korean": "애완동물 브러시",
        "English": "pet grooming brush",
        "Arabic": "فرشاة الحيوانات الأليفة",
        "Vietnamese": "lược chải lông thú cưng",
        "Thai": "แปรงสัตว์เลี้ยง",
        "Indonesian": "sikat hewan peliharaan",
    },
    "冷链保温箱": {
        "Indonesian": "kotak insulasi rantai dingin",
        "English": "cold chain insulated box",
        "Spanish": "caja aislante para cadena de frío",
        "French": "boîte isolée pour chaîne du froid",
        "German": "Kühlkette-Isolierbox",
        "Japanese": "コールドチェーン保冷ボックス",
        "Korean": "콜드체인 보온 박스",
        "Portuguese": "caixa isolada para cadeia de frio",
        "Arabic": "صندوق عزل سلسلة التبريد",
        "Vietnamese": "thùng cách nhiệt chuỗi lạnh",
        "Thai": "กล่องฉนวนโซ่เย็น",
    },
    # English → {language: localized}
    "hydraulic fitting": {
        "Spanish": "racores hidráulicos",
        "French": "raccords hydrauliques",
        "German": "Hydraulikanschlüsse",
        "Japanese": "油圧継手",
        "Korean": "유압 피팅",
        "Portuguese": "conexões hidráulicas",
        "English": "hydraulic fittings",
    },
    "hydraulic fittings": {
        "Spanish": "racores hidráulicos",
        "French": "raccords hydrauliques",
        "German": "Hydraulikanschlüsse",
        "Japanese": "油圧継手",
        "English": "hydraulic fittings",
    },
    "steel pipe": {
        "Japanese": "鉄管",
        "Spanish": "tubos de acero",
        "German": "Stahlrohre",
        "English": "steel pipes",
    },
    "steel pipes": {
        "Japanese": "鉄管",
        "Spanish": "tubos de acero",
        "German": "Stahlrohre",
        "English": "steel pipes",
    },
    "ceramic mug": {
        "Spanish": "tazas de cerámica",
        "French": "tasses en céramique",
        "German": "Keramiktassen",
        "Japanese": "セラミックカップ",
        "English": "ceramic mugs",
    },
    "industrial belt": {
        "German": "Industriegurte",
        "Japanese": "工業用ベルト",
        "Spanish": "correas industriales",
        "English": "industrial belts",
    },
    "pet grooming brush": {
        "Portuguese": "escova para animais de estimação",
        "Spanish": "cepillo para mascotas",
        "German": "Haustierbürste",
        "English": "pet grooming brush",
    },
    "cold chain insulated box": {
        "Indonesian": "kotak insulasi rantai dingin",
        "English": "cold chain insulated box",
        "Spanish": "caja aislante para cadena de frío",
    },
}


def _lookup_glossary(product_original: str, target_language: str) -> Optional[str]:
    """Look up product in the builtin glossary. Returns None if not found."""
    key = product_original.strip()
    # Exact match
    if key in _BUILTIN_GLOSSARY:
        return _BUILTIN_GLOSSARY[key].get(target_language)
    # Case-insensitive match
    key_lower = key.lower()
    for k, v in _BUILTIN_GLOSSARY.items():
        if k.lower() == key_lower:
            return v.get(target_language)
    return None


def _is_builtin_product(product_original: str) -> bool:
    """Check if a product exists in the builtin glossary for ANY language."""
    key = product_original.strip()
    if key in _BUILTIN_GLOSSARY:
        return True
    key_lower = key.lower()
    return any(k.lower() == key_lower for k in _BUILTIN_GLOSSARY)


# ═══════════════════════════════════════════════════════════════════
# Provider interface
# ═══════════════════════════════════════════════════════════════════

class TranslationProvider:
    """Abstract provider for structured product term translation.

    Subclass and override translate_product_term() for real LLM/API calls.
    The default implementation returns None (fallback to original).
    """

    def translate_product_term(
        self,
        product_original: str,
        target_language: str,
        context: Optional[dict] = None,
    ) -> Optional[dict]:
        """Translate a product term to the target language.

        Returns dict with keys: product_localized, confidence
        Returns None if translation is not possible.
        """
        return None


class MockTranslationProvider(TranslationProvider):
    """Mock provider for testing — returns predefined translations.

    Does NOT require network. Translations are explicitly defined
    for known test products and return None for anything else,
    forcing fallback_original with translation_missing=True.
    """

    # Predefined mock translations for test products
    _MOCK_TRANSLATIONS = {
        ("石墨坩埚", "German"): {"product_localized": "Graphittiegel", "confidence": 0.88},
        ("graphite crucible", "German"): {"product_localized": "Graphittiegel", "confidence": 0.88},
        ("硅胶密封圈", "French"): {"product_localized": "joints d'étanchéité en silicone", "confidence": 0.86},
        ("silicone seal ring", "French"): {"product_localized": "joints d'étanchéité en silicone", "confidence": 0.86},
        ("silicone sealing ring", "French"): {"product_localized": "joints d'étanchéité en silicone", "confidence": 0.86},
        ("anti-static turnover box", "Vietnamese"): {"product_localized": "thùng chứa chống tĩnh điện", "confidence": 0.84},
        ("anti-static turnover boxes", "Vietnamese"): {"product_localized": "thùng chứa chống tĩnh điện", "confidence": 0.84},
        ("冷链保温箱", "Indonesian"): {"product_localized": "kotak insulasi rantai dingin", "confidence": 0.85},
        ("cold chain insulated box", "Indonesian"): {"product_localized": "kotak insulasi rantai dingin", "confidence": 0.85},
    }

    def translate_product_term(
        self,
        product_original: str,
        target_language: str,
        context: Optional[dict] = None,
    ) -> Optional[dict]:
        key = (product_original.strip(), target_language)
        # Exact match first
        if key in self._MOCK_TRANSLATIONS:
            return dict(self._MOCK_TRANSLATIONS[key])
        # Case-insensitive match
        key_lower = (product_original.strip().lower(), target_language)
        for (prod, lang), val in self._MOCK_TRANSLATIONS.items():
            if prod.lower() == product_original.strip().lower() and lang == target_language:
                return dict(val)
        return None


# ═══════════════════════════════════════════════════════════════════
# Core localization function
# ═══════════════════════════════════════════════════════════════════

def _normalize_language_name(lang: str) -> str:
    """Normalize a language name to the canonical English form."""
    if not lang:
        return "English"
    from lib.language_normalizer import normalize
    result = normalize(lang)
    return result.get("language", "English")


def localize_product_name(
    product_original: str,
    target_language: str,
    market: Optional[str] = None,
    industry: Optional[str] = None,
    provider: Optional[TranslationProvider] = None,
) -> ProductLocalizationResult:
    """Localize a product name to the target language.

    Resolution order:
    1. Builtin glossary lookup (high-frequency fallback)
    2. Provider (LLM structured translation or mock)
    3. Fallback to original with translation_missing=True

    Args:
        product_original: Raw product name from user input
        target_language: Target language (English, Japanese, Spanish, etc.)
        market: Optional market (not used in product_localized, informational only)
        industry: Optional industry context for the provider
        provider: Optional TranslationProvider instance

    Returns:
        ProductLocalizationResult with translation details
    """
    # Guard: empty or None product
    if not product_original or not str(product_original).strip():
        return ProductLocalizationResult(
            product_original=str(product_original or ""),
            product_localized="Product",
            target_language=target_language or "English",
            locale="en-US",
            method="fallback_original",
            confidence=0.0,
            translation_missing=True,
        )

    original = str(product_original).strip()
    language = _normalize_language_name(target_language)

    # Get locale
    from lib.language_normalizer import normalize
    norm = normalize(language)
    locale = norm.get("locale", "en-US")

    # If target language is Chinese, no translation needed for Chinese products
    from lib.localization import normalize_language as _norm_loc_lib
    writer_lang = _norm_loc_lib(language)
    if writer_lang in ("Chinese Simplified", "Chinese Traditional"):
        # For CJK products where source == target, product_localized = product_original
        return ProductLocalizationResult(
            product_original=original,
            product_localized=original,
            target_language=language,
            locale=locale,
            method="builtin_glossary",
            confidence=1.0,
            translation_missing=False,
        )

    # 1. Builtin glossary lookup
    glossary_result = _lookup_glossary(original, language)
    if glossary_result:
        return ProductLocalizationResult(
            product_original=original,
            product_localized=glossary_result,
            target_language=language,
            locale=locale,
            method="builtin_glossary",
            confidence=0.95,
            translation_missing=False,
        )

    # 2. Provider
    if provider:
        context = {}
        if industry:
            context["industry"] = industry
        if market:
            context["market"] = market

        try:
            provider_result = provider.translate_product_term(original, language, context)
        except Exception:
            provider_result = None

        if provider_result and isinstance(provider_result, dict):
            localized = provider_result.get("product_localized", "").strip()
            confidence = float(provider_result.get("confidence", 0.7))
            if localized and localized != original:
                return ProductLocalizationResult(
                    product_original=original,
                    product_localized=localized,
                    target_language=language,
                    locale=locale,
                    method="llm_structured_translation",
                    confidence=min(max(confidence, 0.0), 1.0),
                    translation_missing=False,
                )

    # 3. Fallback: keep original, mark as missing
    return ProductLocalizationResult(
        product_original=original,
        product_localized=original,
        target_language=language,
        locale=locale,
        method="fallback_original",
        confidence=0.0,
        translation_missing=True,
    )


# ═══════════════════════════════════════════════════════════════════
# Prompt builder (for real LLM providers — not used by mock)
# ═══════════════════════════════════════════════════════════════════

def build_product_translation_prompt(
    product_original: str,
    target_language: str,
    market: Optional[str] = None,
    industry: Optional[str] = None,
) -> str:
    """Build a structured prompt for product name translation.

    Returns a prompt string suitable for an LLM translation call.
    The expected response format is JSON with product_localized and confidence.
    """
    context_parts = []
    if industry:
        context_parts.append(f"industry: {industry}")
    if market:
        context_parts.append(f"target market: {market}")
    context_str = ", ".join(context_parts) if context_parts else "general B2B export"

    return (
        f"Translate the following product name from its source language "
        f"into {target_language} for a B2B export website.\n\n"
        f"Product: {product_original}\n"
        f"Context: {context_str}\n\n"
        f"Rules:\n"
        f"- Return ONLY a JSON object with keys: product_localized, confidence\n"
        f"- product_localized must be the natural trade term in {target_language}\n"
        f"- Do NOT include the market name, language name, or site type in the translation\n"
        f"- confidence is a float 0.0-1.0\n"
        f"- If unsure, set confidence below 0.5\n\n"
        f'Example response: {{"product_localized": "Graphittiegel", "confidence": 0.88}}'
    )


def parse_product_translation_response(response: str) -> Optional[dict]:
    """Parse a provider response string into a dict.

    Handles JSON responses, with or without markdown code fences.
    Returns None if parsing fails.
    """
    import json

    if not response or not response.strip():
        return None

    text = response.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try JSON parse
    try:
        result = json.loads(text)
        if isinstance(result, dict) and "product_localized" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    m = re.search(r'\{[^{}]*"product_localized"[^{}]*\}', text)
    if m:
        try:
            result = json.loads(m.group(0))
            if isinstance(result, dict) and "product_localized" in result:
                return result
        except json.JSONDecodeError:
            pass

    return None


# ═══════════════════════════════════════════════════════════════════
# Validation and quality checks
# ═══════════════════════════════════════════════════════════════════

def validate_product_translation(
    product_original: str,
    product_localized: str,
    target_language: str,
) -> bool:
    """Basic validation that a translation is plausible.

    Returns False if:
    - localized is empty or equals original (for non-Chinese targets)
    - localized is "None" or "null"
    """
    if not product_localized or not product_localized.strip():
        return False

    localized = product_localized.strip()

    # Never allow literal "None" or "null"
    if localized.lower() in ("none", "null", "undefined"):
        return False

    # For non-Chinese targets, localized should differ from original
    # (unless original is already in the target language)
    if target_language not in ("Chinese", "Chinese Simplified", "Chinese Traditional"):
        if localized == product_original.strip():
            # Allowed only if original is already in target language
            # (e.g., English product → English target)
            return True

    return True


def has_source_language_leak(
    text: str,
    source_language: str,
    target_language: str,
) -> bool:
    """Check if a source-language product name leaks into target-language text.

    Detects Chinese characters in non-Chinese target language pages,
    or other script mismatches.

    Technical acronyms (MOQ, OEM, ODM, ASTM, JIS, DIN, EN, BSP, NPT, JIC,
    ISO, FDA, CE) are excluded from leak detection.
    """
    if not text or not source_language or not target_language:
        return False

    # If source == target, no leak is possible
    if source_language == target_language:
        return False

    # TECHNICAL_ACRONYMS that are allowed in any language
    _TECH_ACRONYMS = {
        "MOQ", "OEM", "ODM", "ASTM", "JIS", "DIN", "EN", "BSP", "NPT", "JIC",
        "ISO", "FDA", "CE", "GSM", "TPR", "PVC", "PU", "BPA", "LED",
        "MTC", "B2B", "SEO", "ROI", "API", "SKU", "UPC", "EAN",
    }

    # Remove tech acronyms before checking
    clean_text = text
    for acronym in _TECH_ACRONYMS:
        clean_text = re.sub(r'\b' + re.escape(acronym) + r'\b', '', clean_text, flags=re.IGNORECASE)

    # Detect CJK in non-CJK target
    cjk_target_langs = {"Chinese", "Chinese Simplified", "Chinese Traditional", "Japanese", "Korean"}
    cjk_source_langs = {"Chinese", "Chinese Simplified", "Chinese Traditional", "Japanese", "Korean"}

    if target_language not in cjk_target_langs and source_language in cjk_source_langs:
        # Check for CJK characters
        if re.search(r'[一-鿿぀-ゟ゠-ヿ가-힯]', clean_text):
            return True

    # Detect Arabic in non-Arabic target
    if target_language != "Arabic" and source_language == "Arabic":
        if re.search(r'[؀-ۿ]', clean_text):
            return True

    return False


def product_translation_missing(result: ProductLocalizationResult) -> bool:
    """Check if a localization result indicates missing translation."""
    if not result:
        return True
    return result.translation_missing


def get_product_name_for_page(
    intent: dict,
    language: str,
    provider: Optional[TranslationProvider] = None,
) -> str:
    """Get the best product name for page content generation.

    Priority:
    1. product_localized (if available and not missing)
    2. product_display_name (cleaned internal name)
    3. product_original (raw extracted name)
    4. "Product" (fallback)

    Never returns None.
    """
    # Check for stored product_localized in intent
    product_localized = intent.get("product_localized") if intent else None
    if product_localized and str(product_localized).strip() and str(product_localized).lower() != "none":
        return str(product_localized).strip()

    # If not stored yet, try to localize
    product_original = (intent or {}).get("product") or (intent or {}).get("product_phrase")
    if product_original and str(product_original).strip():
        original = str(product_original).strip()
        result = localize_product_name(original, language, provider=provider)
        if not result.translation_missing and result.product_localized != original:
            return result.product_localized
        return original

    # Fallback to display name
    from lib.intent_engine import get_product_display_name
    display = get_product_display_name(intent)
    if display and str(display).strip() and str(display).lower() != "none":
        return str(display).strip()

    return "Product"


# ═══════════════════════════════════════════════════════════════════
# Quality detection helpers
# ═══════════════════════════════════════════════════════════════════

def assert_no_none_terms(text: str) -> bool:
    """Verify that no 'None' literal appears in generated content."""
    if not text:
        return True
    # Check for the literal word "None" as a standalone word
    # (not inside other words like "NoneType")
    return not bool(re.search(r'\bNone\b', str(text)))


def product_localization_coverage(text: str, product_localized: str) -> float:
    """Score how well the localized product name appears in the content.

    Returns 0.0-1.0 based on presence of the localized product name.
    """
    if not text or not product_localized:
        return 0.0

    clean_text = str(text).casefold()
    localized = str(product_localized).strip()

    if not localized:
        return 0.0

    # Count occurrences of the localized product name
    count = clean_text.count(localized.casefold())

    # Score: 1 occurrence → 0.5, 3+ → 1.0
    if count >= 3:
        return 1.0
    elif count >= 1:
        return 0.5 + min(count - 1, 2) * 0.25
    return 0.0


def source_language_leak_score(
    text: str,
    product_original: str,
    target_language: str,
) -> float:
    """Score the degree of source-language leakage in target-language content.

    Returns 0.0 (no leak) to 1.0 (severe leak).
    Only checks for CJK characters in non-CJK target pages.
    Technical acronyms are excluded.
    """
    if not text or not product_original or not target_language:
        return 0.0

    _TECH_ACRONYMS = {
        "MOQ", "OEM", "ODM", "ASTM", "JIS", "DIN", "EN", "BSP", "NPT", "JIC",
        "ISO", "FDA", "CE", "GSM", "TPR", "PVC", "PU", "BPA", "LED",
        "MTC", "B2B", "SEO", "ROI", "API", "SKU", "UPC", "EAN",
    }

    clean_text = str(text)
    for acronym in _TECH_ACRONYMS:
        clean_text = re.sub(r'\b' + re.escape(acronym) + r'\b', '', clean_text, flags=re.IGNORECASE)

    cjk_target_langs = {"Chinese", "Chinese Simplified", "Chinese Traditional", "Japanese", "Korean"}

    # Only check non-CJK targets
    if target_language in cjk_target_langs:
        return 0.0

    # Count CJK characters
    cjk_chars = re.findall(r'[一-鿿぀-ゟ゠-ヿ가-힯]', clean_text)
    if not cjk_chars:
        return 0.0

    # Score based on CJK character density
    total_chars = len(re.sub(r'\s', '', clean_text))
    if total_chars == 0:
        return 0.0

    ratio = len(cjk_chars) / total_chars
    return min(ratio * 3, 1.0)  # Scale up — even 30% CJK is severe
