# -*- coding: utf-8 -*-
"""lib/serp_provider.py · Phase 5: SERP Provider 抽象层

Base → Mock / Manual / Optional (google_cse, etc.)
所有 provider 返回 list[SERPResult]。
"""

import time
import re
from lib.competitor_schema import SERPResult


# ── Base ─────────────────────────────────────────────


class BaseSERPProvider:
    def search(self, query: str, market: str = None, language: str = None,
               limit: int = 10) -> list[SERPResult]:
        raise NotImplementedError


# ── Mock ─────────────────────────────────────────────


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().split()) or "B2B product supplier"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _mock_serp_rows(query: str) -> list[tuple[str, str, str]]:
    """Build deterministic mock SERP rows from the active query."""
    topic = _normalize_query(query)
    display = topic.title()
    topic_lower = topic.lower()
    focus = "Hammer" if "hardware" in topic_lower and "tool" in topic_lower else display.split()[0]
    slug = _slugify(topic)

    return [
        (
            f"{display} Guide for B2B Buyers",
            f"https://buyersguide.example/{slug}-guide",
            f"Mock snippet for: {topic} guide, wholesale sourcing, manufacturer capabilities, and export support.",
        ),
        (
            f"{focus} Manufacturer and Wholesale {display} Export",
            f"https://toolsource.example/{slug}-manufacturer-wholesale",
            f"Mock snippet for: {focus.lower()} manufacturer, {topic} wholesale, B2B export terms, and bulk order requirements.",
        ),
        (
            f"Industrial {display} Specifications",
            f"https://industrialtools.example/{slug}-specifications",
            f"Mock snippet for: industrial {topic} specifications, packaging, MOQ, OEM, and export documentation.",
        ),
        (
            f"How to Choose a {display}",
            f"https://sourcingmanual.example/choose-{slug}",
            f"Mock snippet for: comparing {topic} quality systems, supplier capacity, manufacturer audits, and samples.",
        ),
        (
            f"{display} OEM and Packaging Requirements",
            f"https://oemsourcing.example/{slug}-oem-packaging",
            f"Mock snippet for: {topic} OEM options, private labeling, export packaging, and quality control.",
        ),
        (
            f"{display} Wholesale Pricing and MOQ",
            f"https://wholesalebuyers.example/{slug}-pricing-moq",
            f"Mock snippet for: {topic} wholesale pricing, MOQ planning, bulk order quantities, and payment terms.",
        ),
        (
            f"{display} Export Documentation Guide",
            f"https://exportdesk.example/{slug}-export-documents",
            f"Mock snippet for: {topic} export documentation, certificates, customs paperwork, and shipping support.",
        ),
        (
            f"{display} Supplier and Manufacturer Comparison",
            f"https://supplycompare.example/{slug}-supplier-comparison",
            f"Mock snippet for: {topic} supplier comparison, manufacturer capabilities, lead times, and compliance.",
        ),
        (
            f"{display} Quality Control for B2B Buyers",
            f"https://qualitybuyers.example/{slug}-quality-control",
            f"Mock snippet for: {topic} inspections, specifications, testing, and B2B buyer acceptance criteria.",
        ),
        (
            f"{display} Bulk Order Checklist",
            f"https://bulkorders.example/{slug}-bulk-order-checklist",
            f"Mock snippet for: {topic} bulk order planning, packaging, wholesale terms, and export delivery.",
        ),
    ]


class MockSERPProvider(BaseSERPProvider):
    """测试用 mock provider, 返回稳定假数据。"""

    def search(self, query: str, market: str = None, language: str = None,
               limit: int = 10) -> list[SERPResult]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        results = []
        for i, (title, url, snippet) in enumerate(_mock_serp_rows(query)[:limit]):
            domain = url.split("/")[2] if "://" in url else url
            results.append(SERPResult(
                rank=i + 1, title=title, url=url, domain=domain,
                snippet=snippet,
                source="mock", fetched_at=now,
            ))
        return results


# ── Manual ───────────────────────────────────────────


class ManualSERPProvider(BaseSERPProvider):
    """接收用户传入 URL 列表。"""

    def __init__(self, urls: list[str] = None):
        self._urls = urls or []

    def search(self, query: str, market: str = None, language: str = None,
               limit: int = 10) -> list[SERPResult]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        results = []
        for i, url in enumerate(self._urls[:limit]):
            domain = url.split("/")[2] if "://" in url else url
            results.append(SERPResult(
                rank=i + 1, title=f"Manual URL {i+1}", url=url, domain=domain,
                snippet="", source="manual", fetched_at=now,
            ))
        return results


# ── Factory ──────────────────────────────────────────


_PROVIDER_REGISTRY = {
    "mock": MockSERPProvider,
    "manual": ManualSERPProvider,
}


def get_serp_provider(name: str = None, urls: list[str] = None) -> BaseSERPProvider:
    """获取 SERP provider。"""
    if urls:
        return ManualSERPProvider(urls)
    if name and name in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[name]()
    return MockSERPProvider()


def search_serp(query: str, market: str = None, language: str = None,
                limit: int = 10, provider: BaseSERPProvider = None) -> list[SERPResult]:
    """便捷搜索函数。"""
    if provider is None:
        provider = get_serp_provider()
    return provider.search(query, market=market, language=language, limit=limit)
