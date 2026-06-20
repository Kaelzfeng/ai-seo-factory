# -*- coding: utf-8 -*-
"""tests/test_phase4_integration.py · Phase 4 integration tests"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import tempfile

import pytest

import run as _run
import models

_MOCK_CONTENT = {
    "title": "Test Page",
    "meta_description": "Test meta description for SEO, 150+ chars of meaningful content.",
    "html": "<h1>Test</h1><h2>Section</h2><p>Content " * 10 + "</p>",
    "image_query": "test image",
}

_MOCK_QUALITY = {"score": 85.0, "breakdown": {}, "issues": [], "passed": True}


@pytest.fixture
def isolated_db(monkeypatch):
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    yield conn
    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


def test_generate_site_from_blueprint_basic(monkeypatch, isolated_db):
    """generate_site_from_blueprint 基本流程不崩溃。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint

    profile = BusinessProfile(industry="PU leather", languages=["English"],
                              target_markets=["global"], products=["PU leather"])
    pages = [
        PagePlan(slug="guide", title="Guide", page_type="guide", primary_keyword="pu leather guide"),
        PagePlan(slug="vs", title="VS", page_type="comparison", primary_keyword="pu leather vs pvc"),
    ]
    bp = SiteBlueprint(project_id=1, business_profile=profile, pages=pages,
                       link_graph={"guide": ["vs"], "vs": ["guide"]})

    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}
    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    assert result["pages_total"] == 2
    assert result["pages_success"] == 2


def test_page_contents_storage(monkeypatch, isolated_db):
    """page_contents 存取正常。"""
    tid = models.create_tenant("pc-test")
    pid = models.create_page_content(
        tenant_id=tid, slug="test", page_type="article",
        title="Test", primary_keyword="test",
    )
    pc = models.get_page_content(pid)
    assert pc is not None
    assert pc["slug"] == "test"


def test_page_contents_tenant_isolation(monkeypatch, isolated_db):
    """tenant 隔离正常工作。"""
    tid1 = models.create_tenant("pc-t1")
    tid2 = models.create_tenant("pc-t2")
    pid = models.create_page_content(tenant_id=tid1, slug="t1")

    pcs = models.list_page_contents(tenant_id=tid2)
    assert len(pcs) == 0

    pcs = models.list_page_contents(tenant_id=tid1)
    assert len(pcs) >= 1
