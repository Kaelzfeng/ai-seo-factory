# -*- coding: utf-8 -*-
"""tests/test_gutenberg_emitter.py · Gutenberg emitter tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.gutenberg_emitter import (
    html_to_gutenberg_blocks, page_content_to_gutenberg, strip_gutenberg_comments,
)
from lib.seo_engine.schemas import PageContent


def test_html_to_blocks_h2():
    result = html_to_gutenberg_blocks("<h2>Section Title</h2>")
    assert '<!-- wp:heading' in result
    assert '<h2>' in result
    assert '<!-- /wp:heading -->' in result


def test_html_to_blocks_p():
    result = html_to_gutenberg_blocks("<p>Hello world</p>")
    assert '<!-- wp:paragraph -->' in result
    assert '<!-- /wp:paragraph -->' in result


def test_html_to_blocks_ul():
    result = html_to_gutenberg_blocks("<ul><li>A</li><li>B</li></ul>")
    assert '<!-- wp:list -->' in result


def test_html_to_blocks_table():
    result = html_to_gutenberg_blocks("<table><tr><td>X</td></tr></table>")
    assert '<!-- wp:table -->' in result


def test_page_content_to_gutenberg():
    pc = PageContent(slug="t", body_html="<h1>Title</h1><p>Body</p>")
    result = page_content_to_gutenberg(pc)
    assert '<!-- wp:heading' in result


def test_strip_gutenberg_comments():
    gb = '<!-- wp:paragraph -->\n<p>Hello</p>\n<!-- /wp:paragraph -->'
    clean = strip_gutenberg_comments(gb)
    assert '<p>Hello</p>' in clean
    assert '<!-- wp:' not in clean


def test_empty_html():
    assert html_to_gutenberg_blocks("") == ""
    assert html_to_gutenberg_blocks(None) == ""
