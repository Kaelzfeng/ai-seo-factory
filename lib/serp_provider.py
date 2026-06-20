# -*- coding: utf-8 -*-
"""lib/serp_provider.py · Phase 5: SERP Provider 抽象层

Base → Mock / Manual / Optional (google_cse, etc.)
所有 provider 返回 list[SERPResult]。
"""

import time
from lib.competitor_schema import SERPResult


# ── Base ─────────────────────────────────────────────


class BaseSERPProvider:
    def search(self, query: str, market: str = None, language: str = None,
               limit: int = 10) -> list[SERPResult]:
        raise NotImplementedError


# ── Mock ─────────────────────────────────────────────


_MOCK_SERP = [
    ("PU Leather Supplier Guide — Complete B2B Sourcing", "https://example.com/pu-leather-guide"),
    ("PU Leather vs Genuine Leather: Key Differences", "https://leather101.com/pu-vs-genuine"),
    ("Top 10 PU Leather Manufacturers in China", "https://sourcify.com/pu-leather-manufacturers"),
    ("PU Leather for Furniture: Material Specifications", "https://furniturematerials.com/pu-leather"),
    ("Microfiber PU Leather Wholesale Supplier", "https://alibaba.com/microfiber-pu"),
    ("Is PU Leather Durable? FAQ for B2B Buyers", "https://leatherfaq.com/pu-durability"),
    ("Types of Synthetic Leather — Complete Overview", "https://materialhub.com/synthetic-leather-types"),
    ("PU Leather vs PVC Leather: Comparison Guide", "https://materialcompare.com/pu-vs-pvc"),
    ("Automotive PU Leather Specifications", "https://autoupholstery.com/pu-leather-specs"),
    ("PU Leather Care and Maintenance Tips", "https://cleanipedia.com/pu-leather-care"),
]


class MockSERPProvider(BaseSERPProvider):
    """测试用 mock provider, 返回稳定假数据。"""

    def search(self, query: str, market: str = None, language: str = None,
               limit: int = 10) -> list[SERPResult]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        results = []
        for i, (title, url) in enumerate(_MOCK_SERP[:limit]):
            domain = url.split("/")[2] if "://" in url else url
            results.append(SERPResult(
                rank=i + 1, title=title, url=url, domain=domain,
                snippet=f"Mock snippet for: {title[:60]}...",
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
