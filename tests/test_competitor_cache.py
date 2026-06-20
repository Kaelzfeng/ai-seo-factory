# -*- coding: utf-8 -*-
import sys, os, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lib.competitor_cache as cache


def test_write_and_read(monkeypatch):
    td = tempfile.mkdtemp()
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", Path(td))
    key = cache.get_cache_key("fetch", "https://example.com")
    cache.write_cache(key, {"html": "<p>test</p>"})
    data = cache.read_cache(key)
    assert data == {"html": "<p>test</p>"}


def test_expired_cache(monkeypatch):
    td = tempfile.mkdtemp()
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", Path(td))
    key = cache.get_cache_key("fetch", "https://expired.com")
    # 写入已过期缓存 (cached_at 在过去)
    path = Path(td) / key
    import json as _json
    path.write_text(_json.dumps({"_cached_at": 0, "_ttl": 1, "_payload": {"html": "x"}}))
    data = cache.read_cache(key)
    assert data is None


def test_clear_expired(monkeypatch):
    td = tempfile.mkdtemp()
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", Path(td))
    key = cache.get_cache_key("fetch", "https://exp.com")
    path = Path(td) / key
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({"_cached_at": 0, "_ttl": 1, "_payload": {"html": "x"}}))
    cache.clear_expired_cache()
    assert not path.exists()
