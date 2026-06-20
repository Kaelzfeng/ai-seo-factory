# -*- coding: utf-8 -*-
"""tests/test_stage5_links.py · Stage 5 internal link tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import PageContent, SiteBlueprint, PagePlan, BusinessProfile
from lib.seo_engine.stage5_links import (
    attach_internal_links, attach_links_to_pages, validate_internal_links,
)


def _make_blueprint():
    profile = BusinessProfile(industry="Test")
    pages = [
        PagePlan(slug="guide", title="Guide", page_type="guide", primary_keyword="guide"),
        PagePlan(slug="vs", title="VS", page_type="comparison", primary_keyword="vs"),
        PagePlan(slug="faq", title="FAQ", page_type="faq", primary_keyword="faq"),
    ]
    link_graph = {"guide": ["vs", "faq"], "vs": ["guide"], "faq": ["guide"]}
    return SiteBlueprint(project_id=1, business_profile=profile, pages=pages, link_graph=link_graph)


def test_attach_links_adds_section():
    bp = _make_blueprint()
    pc = PageContent(slug="guide", page_type="guide", body_html="<p>Content</p>")
    result = attach_internal_links(pc, bp)
    assert 'internal-links' in result.body_html.lower() or 'Related Pages' in result.body_html


def test_attach_links_cluster_to_pillar():
    bp = _make_blueprint()
    pc = PageContent(slug="vs", page_type="comparison", body_html="<p>Compare</p>")
    result = attach_internal_links(pc, bp)
    assert "guide" in str(result.internal_links)


def test_validate_links_no_bad_links():
    bp = _make_blueprint()
    pcs = [
        PageContent(slug="guide", internal_links=["vs", "faq"]),
        PageContent(slug="vs", internal_links=["guide"]),
    ]
    result = validate_internal_links(pcs, bp)
    assert result["ok"] is True


def test_validate_links_detects_bad():
    bp = _make_blueprint()
    pcs = [PageContent(slug="guide", internal_links=["nonexistent"])]
    result = validate_internal_links(pcs, bp)
    assert result["ok"] is False
