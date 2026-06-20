# -*- coding: utf-8 -*-
"""lib/serp_scraper.py · Phase 5: 页面抓取 + On-page 解析

尊重 robots.txt, 限速 1 req/s, 磁盘缓存。
不执行 JS, 不做浏览器自动化。
"""

import json
import re
import time
import urllib.robotparser
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from lib.competitor_schema import OnPageSignals
from lib.competitor_cache import get_cache_key, read_cache, write_cache

_RATE_LIMIT_SEC = 1.0
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _RATE_LIMIT_SEC:
        time.sleep(_RATE_LIMIT_SEC - elapsed)
    _last_request_time = time.time()


def can_fetch_url(url: str, user_agent: str = "AISEOFactoryBot") -> bool:
    """检查 robots.txt 是否允许抓取。"""
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # robots.txt 不可用 → 允许抓取
        return True


def fetch_url(url: str, timeout: int = 15, use_cache: bool = True) -> dict:
    """抓取 URL 返回 html 文本。

    Returns:
        {"ok": bool, "html": str, "error": str, "status_code": int}
    """
    # 缓存优先
    if use_cache:
        ck = get_cache_key("fetch", url)
        cached = read_cache(ck)
        if cached:
            return {"ok": True, "html": cached.get("html", ""), "error": "",
                    "status_code": 200, "from_cache": True}

    # robots.txt 检查
    if not can_fetch_url(url):
        return {"ok": False, "html": "", "error": "Blocked by robots.txt", "status_code": 403}

    _rate_limit()

    try:
        import requests
        headers = {"User-Agent": "AISEOFactoryBot/1.0"}
        resp = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        html = resp.text[:500000]  # 截断大页面
        if use_cache:
            ck = get_cache_key("fetch", url)
            write_cache(ck, {"html": html}, ttl_seconds=86400)
        return {"ok": resp.status_code == 200, "html": html,
                "error": "" if resp.status_code == 200 else f"HTTP {resp.status_code}",
                "status_code": resp.status_code}
    except Exception as e:
        return {"ok": False, "html": "", "error": str(e), "status_code": 0}


# ── HTML 解析 ────────────────────────────────────────


class _SignalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.h1 = []
        self.h2 = []
        self.h3 = []
        self.canonical = ""
        self.schema_types = []
        self.faq_items = []
        self.links = []
        self.images = 0
        self._current_tag = ""
        self._in_title = False
        self._text_buffer = []
        self._in_faq = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._current_tag = tag.lower()

        if tag == "meta" and attrs_dict.get("name", "").lower() == "description":
            self.meta_description = attrs_dict.get("content", "")
        if tag == "link" and attrs_dict.get("rel") == "canonical":
            self.canonical = attrs_dict.get("href", "")
        if tag == "img":
            self.images += 1
        if tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith("#"):
                self.links.append(href)
        if tag == "title":
            self._in_title = True
        if tag in ("h1", "h2", "h3"):
            self._text_buffer = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("h1", "h2", "h3"):
            text = " ".join(self._text_buffer).strip()
            if text:
                getattr(self, tag).append(text)
            self._text_buffer = []

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._current_tag in ("h1", "h2", "h3"):
            self._text_buffer.append(data.strip())

    def handle_entityref(self, name):
        if self._in_title:
            self.title += f"&{name};"

    def handle_charref(self, name):
        if self._in_title:
            self.title += f"&#{name};"


def parse_onpage_signals(url: str, html: str) -> OnPageSignals:
    """从 HTML 解析 OnPageSignals。"""
    if not html:
        return OnPageSignals(url=url)

    parser = _SignalParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    # word count (从 text)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    word_count = len(words)

    # schema types
    schema_types = _extract_schema_types(html)

    # faq count
    faq_items = _extract_faq_items(html)
    faq_count = len(faq_items)

    # internal/external links
    base_domain = urlparse(url).netloc
    internal = 0
    external = 0
    for link in parser.links:
        parsed = urlparse(link)
        if not parsed.netloc or parsed.netloc == base_domain:
            internal += 1
        else:
            external += 1

    return OnPageSignals(
        url=url,
        title=parser.title.strip(),
        meta_description=parser.meta_description.strip(),
        h1=list(parser.h1),
        h2=list(parser.h2),
        h3=list(parser.h3),
        word_count=word_count,
        language="en",
        canonical=parser.canonical,
        schema_types=schema_types,
        faq_count=faq_count,
        images_count=parser.images,
        internal_links_count=internal,
        external_links_count=external,
    )


def _extract_schema_types(html: str) -> list[str]:
    """从 HTML 提取 schema.org type。"""
    types = set()
    # JSON-LD
    for m in re.finditer(r'"@type"\s*:\s*"([^"]+)"', html):
        types.add(m.group(1))
    # Microdata
    for m in re.finditer(r'itemtype="https?://schema\.org/([^"]+)"', html):
        types.add(m.group(1))
    return sorted(types)


def _extract_faq_items(html: str) -> list[dict]:
    """从 HTML 提取 FAQ items。"""
    items = []
    # JSON-LD FAQ
    faq_pattern = r'"@type"\s*:\s*"Question".*?"name"\s*:\s*"([^"]+)".*?"@type"\s*:\s*"Answer".*?"text"\s*:\s*"([^"]+)"'
    for m in re.finditer(faq_pattern, html, re.DOTALL):
        items.append({"question": m.group(1)[:200], "answer": m.group(2)[:500]})
    return items


def extract_headings(html: str) -> dict:
    """提取所有 headings。"""
    signals = parse_onpage_signals("", html)
    return {"h1": signals.h1, "h2": signals.h2, "h3": signals.h3}


def extract_meta(html: str) -> dict:
    """提取 meta 信息。"""
    signals = parse_onpage_signals("", html)
    return {"title": signals.title, "meta_description": signals.meta_description,
            "canonical": signals.canonical}


def extract_schema_types(html: str) -> list[str]:
    return _extract_schema_types(html)


def extract_faq_items(html: str) -> list[dict]:
    return _extract_faq_items(html)


def extract_links(html: str, base_url: str = "") -> tuple[int, int]:
    """返回 (internal_count, external_count)。"""
    signals = parse_onpage_signals(base_url, html)
    return signals.internal_links_count, signals.external_links_count


def analyze_url(url: str, use_cache: bool = True) -> dict:
    """一站式 URL 分析。

    Returns:
        {"ok": bool, "signals": OnPageSignals, "error": str}
    """
    result = fetch_url(url, use_cache=use_cache)
    if not result["ok"]:
        return {"ok": False, "signals": None, "error": result["error"]}
    signals = parse_onpage_signals(url, result["html"])
    return {"ok": True, "signals": signals, "error": ""}
