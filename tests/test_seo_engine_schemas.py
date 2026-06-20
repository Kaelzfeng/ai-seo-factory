# -*- coding: utf-8 -*-
"""tests/test_seo_engine_schemas.py · Schema serialization tests

1. BusinessProfile 可序列化
2. SiteBlueprint 可序列化
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.seo_engine.schemas import (
    BusinessProfile, Keyword, Topic, PagePlan, SiteBlueprint, QualityReport,
)


def test_business_profile_to_dict_and_back():
    bp = BusinessProfile(
        industry="PU leather",
        business_type="B2B",
        target_markets=["global", "US"],
        languages=["English"],
        products=["PU leather", "microfiber"],
        buyer_personas=["Furniture importers"],
        value_propositions=["ISO certified"],
        tone="Professional",
        terminology=["GSM", "abrasion resistance"],
    )
    d = bp.to_dict()
    assert d["industry"] == "PU leather"
    assert len(d["target_markets"]) == 2
    assert len(d["terminology"]) == 2

    bp2 = BusinessProfile.from_dict(d)
    assert bp2.industry == bp.industry
    assert bp2.target_markets == bp.target_markets


def test_keyword_to_dict_and_back():
    kw = Keyword(keyword="pu leather supplier", intent="commercial", priority=10)
    d = kw.to_dict()
    assert d["keyword"] == "pu leather supplier"
    kw2 = Keyword.from_dict(d)
    assert kw2.intent == "commercial"


def test_topic_to_dict_and_back():
    t = Topic(id="t-001", name="PU Leather Guide", intent="guide",
              keywords=["pu leather", "synthetic leather"], page_type="guide")
    d = t.to_dict()
    assert d["id"] == "t-001"
    t2 = Topic.from_dict(d)
    assert t2.keywords == t.keywords


def test_page_plan_to_dict_and_back():
    pp = PagePlan(slug="pu-leather-guide", title="PU Leather Guide",
                  page_type="guide", primary_keyword="pu leather",
                  secondary_keywords=["synthetic leather"],
                  suggested_sections=["Overview", "Specifications"])
    d = pp.to_dict()
    assert d["slug"] == "pu-leather-guide"
    pp2 = PagePlan.from_dict(d)
    assert pp2.page_type == "guide"


def test_site_blueprint_to_dict_and_back():
    profile = BusinessProfile(industry="PU leather")
    pages = [PagePlan(slug="p1", title="Test", page_type="guide")]
    bp = SiteBlueprint(
        project_id=1, business_profile=profile,
        pages=pages, link_graph={"p1": []}
    )
    d = bp.to_dict()
    assert d["project_id"] == 1
    assert d["business_profile"] is not None
    assert len(d["pages"]) == 1

    bp2 = SiteBlueprint.from_dict(d)
    assert bp2.project_id == 1
    assert len(bp2.pages) == 1
    assert bp2.business_profile.industry == "PU leather"


def test_quality_report_placeholder():
    qr = QualityReport()
    d = qr.to_dict()
    assert d["score"] == 0.0
    assert d["passed"] is False
