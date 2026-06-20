# -*- coding: utf-8 -*-
"""lib/competitor_analysis.py · Phase 5: 竞品拆解核心逻辑

SERP → 抓取 → OnPageSignals → CompetitorProfile → keywords/intent/weakness
"""

import re
import time
from collections import Counter

from lib.competitor_schema import (
    SERPResult, OnPageSignals, CompetitorProfile, CompetitorReport,
)
from lib.serp_provider import search_serp, get_serp_provider
from lib.serp_scraper import analyze_url
from lib.competitor_cache import get_cache_key, read_cache, write_cache

# 停用词 (最小集)
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "with", "from", "by", "at", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "because", "but", "while", "if", "this",
    "that", "it", "its", "about", "up", "out", "also", "which", "their",
}


# ── 关键词反推 ────────────────────────────────────────


def infer_keywords_from_signals(signals: OnPageSignals) -> list[str]:
    """从 title/meta/h1/h2/h3 提取关键词。"""
    text = " ".join([
        signals.title,
        signals.meta_description,
        *signals.h1, *signals.h2[:5], *signals.h3[:5],
    ]).lower()

    # 提取 2-4 词短语
    words = re.findall(r'[a-z]{3,}', text)
    keywords = Counter()

    # 单关键词
    for w in words:
        if w not in _STOPWORDS:
            keywords[w] += 1

    # 双词短语
    for i in range(len(words) - 1):
        if words[i] not in _STOPWORDS or words[i + 1] not in _STOPWORDS:
            phrase = f"{words[i]} {words[i + 1]}"
            keywords[phrase] += 1

    # 按频率排序, 取 top 15
    top = [kw for kw, _ in keywords.most_common(15)]
    return top


def classify_competitor_intents(keywords: list[str]) -> list[str]:
    """按 intent 归类关键词。"""
    intents = set()
    faq_words = {"what", "why", "how", "is", "are", "can", "does", "will", "should", "durable", "waterproof"}
    comparison_words = {"vs", "versus", "compare", "difference", "better than"}
    commercial_words = {"best", "top", "review", "price", "cost", "buy", "supplier", "manufacturer", "wholesale"}
    guide_words = {"guide", "complete", "types", "overview", "how to"}

    for kw in keywords:
        kwl = kw.lower()
        if any(w in kwl.split() for w in faq_words):
            intents.add("faq")
        elif any(w in kwl for w in comparison_words):
            intents.add("comparison")
        elif any(w in kwl for w in commercial_words):
            intents.add("commercial")
        elif any(w in kwl for w in guide_words):
            intents.add("guide")
        else:
            intents.add("informational")
    return sorted(intents)


# ── 评分 ──────────────────────────────────────────────


def score_content_depth(signals: OnPageSignals) -> float:
    """内容深度评分 0-100。"""
    score = 0.0
    if signals.word_count > 2000:
        score += 30
    elif signals.word_count > 1000:
        score += 20
    elif signals.word_count > 500:
        score += 10
    if len(signals.h2) >= 5:
        score += 25
    elif len(signals.h2) >= 3:
        score += 15
    if signals.faq_count >= 3:
        score += 20
    elif signals.faq_count >= 1:
        score += 10
    if len(signals.schema_types) >= 2:
        score += 15
    elif len(signals.schema_types) >= 1:
        score += 8
    if signals.internal_links_count >= 10:
        score += 10
    return min(100, score)


def score_structure(signals: OnPageSignals) -> float:
    """页面结构评分 0-100。"""
    score = 0.0
    if signals.title:
        score += 20
    if signals.meta_description:
        score += 15
    if signals.h1:
        score += 15
    if len(signals.h2) >= 3:
        score += 20
    if len(signals.schema_types) >= 1:
        score += 10
    if signals.canonical:
        score += 10
    if signals.images_count >= 3:
        score += 10
    return min(100, score)


def identify_weaknesses(signals: OnPageSignals) -> list[str]:
    """识别页面弱点。"""
    weaknesses = []
    if not signals.meta_description:
        weaknesses.append("Missing meta description")
    if not signals.h1:
        weaknesses.append("Missing H1 tag")
    if signals.faq_count == 0:
        weaknesses.append("No FAQ content")
    if len(signals.schema_types) == 0:
        weaknesses.append("No schema.org markup")
    if signals.word_count < 500:
        weaknesses.append(f"Thin content ({signals.word_count} words)")
    if signals.internal_links_count < 3:
        weaknesses.append(f"Few internal links ({signals.internal_links_count})")
    if len(signals.title) < 20:
        weaknesses.append("Title too short")
    if len(signals.title) > 70:
        weaknesses.append("Title too long")
    return weaknesses


# ── 竞品画像 ──────────────────────────────────────────


def build_competitor_profile(serp_result: SERPResult,
                             signals: OnPageSignals | None,
                             error: str = "") -> CompetitorProfile:
    """构建竞品画像。"""
    if signals is None:
        return CompetitorProfile(
            domain=serp_result.domain, url=serp_result.url, rank=serp_result.rank,
            title=serp_result.title, error=error,
        )

    keywords = infer_keywords_from_signals(signals)
    intents = classify_competitor_intents(keywords)
    weaknesses = identify_weaknesses(signals)
    depth = score_content_depth(signals)
    structure = score_structure(signals)

    return CompetitorProfile(
        domain=serp_result.domain, url=serp_result.url, rank=serp_result.rank,
        title=signals.title or serp_result.title,
        meta_description=signals.meta_description,
        headings=[*signals.h1, *signals.h2[:3]],
        schema_types=signals.schema_types,
        faq_items=_extract_faq_from_signals(signals),
        keywords=keywords, intents=intents,
        content_depth_score=depth, structure_score=structure,
        weaknesses=weaknesses, raw_signals=signals,
    )


def _extract_faq_from_signals(signals: OnPageSignals) -> list[dict]:
    """从 signals 提取 FAQ items。"""
    # seek FAQ-like h2/h3: 以 ? 结尾的 heading
    faq_items = []
    for h in signals.h2 + signals.h3:
        if h.strip().endswith("?"):
            faq_items.append({"question": h.strip()})
    return faq_items


# ── 主分析函数 ────────────────────────────────────────


def analyze_competitors(query: str, market: str = None, language: str = None,
                        urls: list[str] = None, limit: int = 10,
                        tenant_id: int = None, project_id: int = None,
                        provider_name: str = None) -> CompetitorReport:
    """执行竞品分析。

    1. SERP 搜索
    2. 逐页抓取 + 解析
    3. 构建 CompetitorProfile
    4. 返回 CompetitorReport
    """
    provider = get_serp_provider(name=provider_name or "mock", urls=urls)
    serp_results = provider.search(query, market=market, language=language, limit=limit)

    competitors = []
    errors = []
    success_count = 0

    for sr in serp_results:
        if provider_name == "mock" or (urls and len(urls) > 0):
            # Mock/Manual: 不真实发 HTTP, 构造最小 signals
            signals = OnPageSignals(
                url=sr.url, title=sr.title,
                meta_description=sr.snippet,
                h1=[sr.title],
                h2=["Key Features", "Specifications", "Applications", "FAQ"],
                h3=["What is PU leather?", "How to choose?"],
                word_count=1200, schema_types=["Article", "FAQPage"],
                faq_count=2, internal_links_count=8, external_links_count=3,
                images_count=4,
            )
            error = ""
        else:
            # 真实抓取
            result = analyze_url(sr.url)
            signals = result.get("signals")
            error = result.get("error", "")

        if not error:
            success_count += 1
        else:
            errors.append(f"{sr.url}: {error}")

        profile = build_competitor_profile(sr, signals, error)
        competitors.append(profile)

    if success_count == 0:
        status = "failed"
    elif success_count < len(serp_results):
        status = "partial_success"
    else:
        status = "completed"

    return CompetitorReport(
        tenant_id=tenant_id, project_id=project_id,
        query=query, market=market or "global", language=language or "English",
        serp_results=serp_results, competitors=competitors,
        status=status, errors=errors,
    )
