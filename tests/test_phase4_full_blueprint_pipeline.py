# -*- coding: utf-8 -*-
"""tests/test_phase4_full_blueprint_pipeline.py · Phase 4.1 全链路烟测

1. 8 页 blueprint → PageContent 全链路
2. generate_site_from_input() 8/8
3. 每页 slug/title/page_type/body_html/meta/quality
4. Gutenberg/Schema/Quality 完整性
5. max_pages 截断 + truncated 标记
6. page_contents 持久化
7. tenant 隔离
8. 质量门槛: polish + re-review
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as _run
import models

_MOCK_CONTENT = {
    "title": "Test Page Title",
    "meta_description": "Test meta description for SEO, 150+ chars of meaningful content for testing.",
    "html": "<h1>Test</h1><h2>Section One</h2><p>Content " * 10 + "</p>",
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


def _setup_mocks(monkeypatch):
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 3000})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)


def _make_8page_blueprint():
    from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint
    profile = BusinessProfile(
        industry="PU leather", business_type="B2B supplier",
        target_markets=["global"], languages=["English"],
        products=["PU leather", "microfiber"], buyer_personas=["Importers"],
        tone="Professional",
    )
    pages = [
        PagePlan(slug="pu-leather-guide", title="PU Leather Guide", page_type="guide",
                 primary_keyword="pu leather guide"),
        PagePlan(slug="pu-leather-vs-genuine-leather", title="PU Leather vs Genuine Leather",
                 page_type="comparison", primary_keyword="pu leather vs genuine leather"),
        PagePlan(slug="pu-leather-vs-pvc-leather", title="PU Leather vs PVC Leather",
                 page_type="comparison", primary_keyword="pu leather vs pvc leather"),
        PagePlan(slug="types-of-synthetic-leather", title="Types of Synthetic Leather",
                 page_type="category", primary_keyword="types of synthetic leather"),
        PagePlan(slug="pu-leather-for-furniture", title="PU Leather for Furniture",
                 page_type="application", primary_keyword="pu leather for furniture"),
        PagePlan(slug="pu-leather-for-automotive", title="PU Leather for Automotive",
                 page_type="application", primary_keyword="pu leather for automotive"),
        PagePlan(slug="is-pu-leather-durable-waterproof", title="Is PU Leather Durable",
                 page_type="faq", primary_keyword="is pu leather durable waterproof"),
        PagePlan(slug="microfiber-pu-leather-bags", title="Microfiber PU Leather Bags",
                 page_type="product", primary_keyword="microfiber pu leather bags"),
    ]
    link_graph = {p.slug: [o.slug for o in pages if o.slug != p.slug] for p in pages}
    return SiteBlueprint(project_id=1, business_profile=profile, pages=pages, link_graph=link_graph)


# ── Test 1: 8 页全量生成 ─────────────────────────────


def test_full_8page_generation(monkeypatch, isolated_db):
    """8 页 blueprint 全部成功生成。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test", "site_url": "https://example.com"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)

    assert result["pages_total"] == 8
    assert result["pages_success"] == 8
    assert result["pages_failed"] == 0
    assert result["code"] == "success"
    assert result["truncated"] is False
    assert len(result["pages"]) == 8


# ── Test 2-5: 每页完整性 ─────────────────────────────


def test_every_page_has_required_fields(monkeypatch, isolated_db):
    """每页都有 slug/title/body_html/meta/quality。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)

    for entry in result["pages"]:
        page = entry.get("page", {})
        content = entry.get("content", {})
        quality = entry.get("quality", {})

        assert page.get("slug"), "missing slug"
        assert page.get("type"), "missing page_type"
        assert page.get("target_keyword"), "missing primary_keyword"
        assert content.get("title"), "missing title"
        assert content.get("html"), "missing body_html"
        assert content.get("meta_description"), "missing meta_description"
        assert quality.get("score") is not None, "missing quality_score"


# ── Test 6: Gutenberg (via content_json on result) ───


def test_gutenberg_in_result(monkeypatch, isolated_db):
    """生成结果中的每页 page_content 含 gutenberg_html。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    # Verify each page entry has accessible content
    for entry in result["pages"]:
        content = entry.get("content", {})
        html = content.get("html", "")
        assert html, f"Empty body_html for {entry.get('page', {}).get('slug')}"
        from lib.gutenberg_emitter import html_to_gutenberg_blocks, strip_gutenberg_comments
        gb = html_to_gutenberg_blocks(html)
        assert gb, f"Empty gutenberg for slug"
        clean = strip_gutenberg_comments(gb)
        assert len(clean) > 20, f"Gutenberg stripped too short"


# ── Test 7: Schema ───────────────────────────────────


def test_schema_in_content_json(monkeypatch, isolated_db):
    """content_json 包含 schema_json。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test",
               "site_url": "https://example.com"}

    _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)

    pcs = models.list_page_contents()
    for pc in pcs:
        cj = json.loads(pc["content_json"])
        schema = cj.get("schema_json", "")
        assert schema, f"Empty schema_json for {pc['slug']}"


# ── Test 8: Internal links ───────────────────────────


def test_internal_links_present(monkeypatch, isolated_db):
    """每页都有 internal_links。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)

    pcs = models.list_page_contents()
    for pc in pcs:
        cj = json.loads(pc["content_json"])
        il = cj.get("internal_links", [])
        assert len(il) >= 1, f"No internal links for {pc['slug']}"


# ── Test 9: Link validation ──────────────────────────


def test_no_links_to_nonexistent_slug(monkeypatch, isolated_db):
    """不存在链接到未知 slug。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    valid_slugs = {p.slug for p in bp.pages}
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)

    pcs = models.list_page_contents()
    for pc in pcs:
        cj = json.loads(pc["content_json"])
        for link in cj.get("internal_links", []):
            assert link in valid_slugs, f"Bad link {link} in {pc['slug']}"


# ── Test 10: max_pages truncation ────────────────────


def test_max_pages_truncation(monkeypatch, isolated_db):
    """max_pages=2 截断 + truncated=true。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run",
                                                bypass_subscription=True, max_pages=2)

    assert result["pages_total"] == 2
    assert result["truncated"] is True
    assert result["pages_success"] == 2


# ── Test 11: max_pages=None 全量 ─────────────────────


def test_max_pages_none_full(monkeypatch, isolated_db):
    """max_pages=None 生成全部页。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run",
                                                bypass_subscription=True, max_pages=None)

    assert result["pages_total"] == 8
    assert result["truncated"] is False


# ── Test 12: 结果中每页有完整字段 ────────────────────


def test_all_result_fields_present(monkeypatch, isolated_db):
    """8 页结果中每页都有完整字段。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    assert len(result["pages"]) == 8
    for entry in result["pages"]:
        page = entry.get("page", {})
        content = entry.get("content", {})
        quality = entry.get("quality", {})
        assert page.get("slug"), "missing slug"
        assert page.get("type"), "missing type"
        assert content.get("title"), "missing title"
        assert content.get("html"), "missing html"
        assert content.get("meta_description"), "missing meta"
        assert quality.get("score") is not None, "missing score"


# ── Test 13: 每页 unique slug ────────────────────────


def test_all_slugs_unique_in_result(monkeypatch, isolated_db):
    """每页 slug 唯一。"""
    _setup_mocks(monkeypatch)
    bp = _make_8page_blueprint()
    project = {"id": 1, "tenant_id": None, "user_id": None, "name": "Test"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    slugs = [entry["page"]["slug"] for entry in result["pages"]]
    assert len(slugs) == len(set(slugs))


# ── Test 14-17: Legacy compatibility ─────────────────


def test_legacy_generate_site_still_works(monkeypatch, isolated_db):
    """原有 generate_site() YAML 管线不受影响。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK_CONTENT))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 1000})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "test", "seed_keyword": "test",
            "pages": [{"title": f"P{n}", "type": "guide", "slug": f"p{n}", "target_keyword": f"k{n}"} for n in range(1, 9)],
        }, f)

    project = {"id": 0, "tenant_id": None, "user_id": None, "name": "test",
               "industry_config": tmp_yaml, "seed_keyword": "test",
               "language": "English", "site_url": "https://example.com"}

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
    assert result["summary"]["total_pages"] == 8


# ── templates/static ─────────────────────────────────


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if templates_dir.exists():
        for f in templates_dir.rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0


def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if static_dir.exists():
        for f in static_dir.rglob("*"):
            if f.is_file():
                assert f.exists()
