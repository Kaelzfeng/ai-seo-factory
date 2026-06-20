# -*- coding: utf-8 -*-
"""lib/competitor_cache.py · Phase 5: 磁盘缓存

简单 JSON 文件缓存, 默认 .cache/competitor/
"""

import json
import os
import time
from pathlib import Path

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "competitor"


def get_cache_dir() -> Path:
    return DEFAULT_CACHE_DIR


def get_cache_key(kind: str, value: str) -> str:
    """生成缓存文件名(safe)。"""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in value)[:120]
    return f"{kind}_{safe}.json"


def _ensure_dir():
    get_cache_dir().mkdir(parents=True, exist_ok=True)


def read_cache(key: str) -> dict | None:
    """读取缓存, 过期返回 None。"""
    path = get_cache_dir() / key
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ttl = data.get("_ttl", 0)
        cached_at = data.get("_cached_at", 0)
        if ttl > 0 and (time.time() - cached_at) > ttl:
            return None
        return data.get("_payload")
    except (json.JSONDecodeError, IOError):
        return None


def write_cache(key: str, data: dict, ttl_seconds: int = 86400):
    """写入缓存。"""
    _ensure_dir()
    path = get_cache_dir() / key
    payload = {
        "_cached_at": time.time(),
        "_ttl": ttl_seconds,
        "_payload": data,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def clear_expired_cache():
    """清理过期缓存。"""
    _ensure_dir()
    now = time.time()
    for f in get_cache_dir().glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            ttl = data.get("_ttl", 0)
            cached_at = data.get("_cached_at", 0)
            if ttl > 0 and (now - cached_at) > ttl:
                f.unlink()
        except (json.JSONDecodeError, IOError):
            pass
