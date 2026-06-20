# -*- coding: utf-8 -*-
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.serp_provider import (
    MockSERPProvider, ManualSERPProvider, get_serp_provider, search_serp,
)


def test_mock_returns_10():
    p = MockSERPProvider()
    results = p.search("test")
    assert len(results) == 10
    assert results[0].rank == 1
    assert results[0].source == "mock"


def test_mock_respects_limit():
    p = MockSERPProvider()
    results = p.search("test", limit=5)
    assert len(results) == 5


def test_manual_provider():
    p = ManualSERPProvider(["https://a.com", "https://b.com"])
    results = p.search("test")
    assert len(results) == 2
    assert results[0].url == "https://a.com"
    assert results[0].source == "manual"


def test_get_serp_provider_default():
    p = get_serp_provider()
    assert isinstance(p, MockSERPProvider)


def test_get_serp_provider_with_urls():
    p = get_serp_provider(urls=["https://x.com"])
    assert isinstance(p, ManualSERPProvider)


def test_search_serp_convenience():
    results = search_serp("test", limit=5)
    assert len(results) == 5
