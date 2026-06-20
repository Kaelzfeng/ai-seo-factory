# -*- coding: utf-8 -*-
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.serp_scraper import parse_onpage_signals, extract_headings, extract_meta


_HTML_BODY = """<h1>Main Heading</h1>
<h2>Section One</h2><p>Content here for word count. """ + "x " * 400 + """</p>
<h2>Section Two</h2><p>More content for depth analysis. """ + "y " * 400 + """</p>
<h3>Sub Section</h3><p>More content</p>
<a href="/internal">Internal</a>
<a href="https://other.com">External</a>
<img src="a.jpg"><img src="b.jpg">
"""
_HTML = f"""<!DOCTYPE html>
<html><head><title>Test Page Title</title>
<meta name="description" content="Test meta description">
<link rel="canonical" href="https://example.com/test">
<script type="application/ld+json">{{"@type":"Article"}}</script>
</head><body>
{_HTML_BODY}
</body></html>"""


def test_parse_onpage_title():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert signals.title == "Test Page Title"


def test_parse_onpage_meta():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert "Test meta description" in signals.meta_description


def test_parse_h1():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert "Main Heading" in signals.h1


def test_parse_h2():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert len(signals.h2) >= 2


def test_word_count():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert signals.word_count > 100


def test_schema_types():
    signals = parse_onpage_signals("https://example.com/test", _HTML)
    assert "Article" in signals.schema_types


def test_extract_headings():
    h = extract_headings(_HTML)
    assert len(h["h1"]) >= 1
    assert len(h["h2"]) >= 2


def test_extract_meta():
    m = extract_meta(_HTML)
    assert m["title"] == "Test Page Title"


def test_empty_html():
    signals = parse_onpage_signals("", "")
    assert signals.word_count == 0
