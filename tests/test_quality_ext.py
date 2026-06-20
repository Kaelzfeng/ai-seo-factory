# -*- coding: utf-8 -*-
"""tests/test_quality_ext.py · Extended quality tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.quality_ext import (
    sanitize_html, readability_score, duplicate_similarity, extended_quality_check,
)
from lib.seo_engine.schemas import PageContent


def test_sanitize_removes_script():
    html = '<p>Good</p><script>alert("xss")</script>'
    clean = sanitize_html(html)
    assert 'script' not in clean.lower()
    assert '<p>Good</p>' in clean


def test_sanitize_removes_onclick():
    html = '<p onclick="alert(1)">Click</p>'
    clean = sanitize_html(html)
    assert 'onclick' not in clean.lower()


def test_sanitize_removes_javascript_url():
    html = '<a href="javascript:void(0)">link</a>'
    clean = sanitize_html(html)
    assert 'javascript:' not in clean.lower()


def test_readability_score():
    text = "This is a simple test. It should be readable. " * 50
    result = readability_score(text)
    assert result["word_count"] > 0
    assert "flesch_approx" in result
    assert "grade_level" in result


def test_readability_empty():
    result = readability_score("")
    assert result["ok"] is False


def test_duplicate_similarity():
    pc1 = PageContent(body_html="<p>PU leather is a synthetic material used for furniture and automotive applications.</p>")
    pc2 = PageContent(body_html="<p>PU leather is a synthetic material used for furniture and automotive applications.</p>")
    sim = duplicate_similarity(pc1, pc2)
    assert sim > 0.8

    pc3 = PageContent(body_html="<p>Solar panels convert sunlight into electricity through photovoltaic cells.</p>")
    sim2 = duplicate_similarity(pc1, pc3)
    assert sim2 < 0.5


def test_extended_quality_check():
    pc = PageContent(body_html="<p>PU leather guide for B2B buyers. Complete specifications and applications. " * 30 + "</p>")
    result = extended_quality_check(pc)
    assert "readability" in result
    assert "html_safe" in result
    assert result["html_safe"] is True
