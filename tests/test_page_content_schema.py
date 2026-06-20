# -*- coding: utf-8 -*-
"""tests/test_page_content_schema.py · PageContent serialization"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import PageContent


def test_page_content_to_dict_and_back():
    pc = PageContent(slug="test", title="Test Title", page_type="guide",
                     primary_keyword="test", body_html="<p>content</p>",
                     quality_score=85.0)
    d = pc.to_dict()
    assert d["slug"] == "test"
    assert d["body_html"] == "<p>content</p>"
    pc2 = PageContent.from_dict(d)
    assert pc2.slug == pc.slug
    assert pc2.body_html == pc.body_html


def test_page_content_defaults():
    pc = PageContent()
    assert pc.slug == ""
    assert pc.page_type == "article"
    assert pc.review_status == "pending"
