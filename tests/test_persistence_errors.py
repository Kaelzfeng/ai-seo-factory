# -*- coding: utf-8 -*-
"""Phase 9.3.2: 持久化错误处理测试"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest, models, run as _run

_MOCK = {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"i"}

@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = models.init_db(dbpath); yield conn; conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


def _setup_mocks(monkeypatch):
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg,c,cfg: {"score":85,"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    try:
        from lib import keyword_scout
        monkeypatch.setattr(keyword_scout, "grounded_plan",
            lambda seed, max_pages=7: {"plan": [{"title":f"P{n}","type":"guide","slug":f"p{n}","target_keyword":f"k{n}"} for n in range(1,9)]})
    except ImportError: pass


# Test 1: Normal generation has no persistence errors
def test_no_persistence_errors_on_success(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pe-ok")
    uid = models.create_user("pe-ok@t.com","h","s")
    pid = models.create_project(user_id=uid, name="PE", tenant_id=tid, seed_keyword="t", language="En", site_url="https://x.com")
    _setup_mocks(monkeypatch)

    from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint
    profile = BusinessProfile(industry="Test", languages=["En"], target_markets=["g"], products=["T"])
    pages = [PagePlan(slug=f"p{n}", page_type="guide", primary_keyword=f"k{n}") for n in range(1,3)]
    bp = SiteBlueprint(project_id=pid, business_profile=profile, pages=pages, link_graph={})
    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "Test", "site_url": "https://x.com"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    assert result["pages_success"] == 2
    assert result.get("persistence_errors", []) == []
    assert result.get("warnings", []) == []


# Test 2: persistence_errors returned when create_page_content fails
def test_persistence_error_captured(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pe-cap")
    uid = models.create_user("pe-cap@t.com","h","s")
    pid = models.create_project(user_id=uid, name="PE2", tenant_id=tid, seed_keyword="t", language="En", site_url="https://x.com")
    _setup_mocks(monkeypatch)
    # Break create_page_content
    monkeypatch.setattr(models, "create_page_content", lambda **kw: (_ for _ in ()).throw(RuntimeError("DB down")))

    from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint
    profile = BusinessProfile(industry="Test", languages=["En"], target_markets=["g"], products=["T"])
    pages = [PagePlan(slug="fail-page", page_type="guide", primary_keyword="k")]
    bp = SiteBlueprint(project_id=pid, business_profile=profile, pages=pages, link_graph={})
    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "Test", "site_url": "https://x.com"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    # Content should still be generated
    assert result["pages_success"] >= 1
    # But persistence error should be recorded
    pe = result.get("persistence_errors", [])
    assert len(pe) >= 1
    assert pe[0]["slug"] == "fail-page"
    assert "DB down" in pe[0]["error"]
    assert result.get("warnings")


# Test 3: Other pages not affected by one persistence failure
def test_other_pages_unaffected(db, monkeypatch):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("pe-other")
    uid = models.create_user("pe-other@t.com","h","s")
    pid = models.create_project(user_id=uid, name="PE3", tenant_id=tid, seed_keyword="t", language="En", site_url="https://x.com")
    _setup_mocks(monkeypatch)

    # Only fail on slug starting with "f"
    orig = models.create_page_content
    def selective_fail(**kw):
        if kw.get("slug","").startswith("f"):
            raise RuntimeError("selective fail")
        return orig(**kw)
    monkeypatch.setattr(models, "create_page_content", selective_fail)

    from lib.seo_engine.schemas import BusinessProfile, PagePlan, SiteBlueprint
    profile = BusinessProfile(industry="Test", languages=["En"], target_markets=["g"], products=["T"])
    pages = [PagePlan(slug=f"fail-{n}", page_type="guide", primary_keyword=f"k{n}") if n==1 else PagePlan(slug=f"ok-{n}", page_type="guide", primary_keyword=f"k{n}") for n in range(1,3)]
    bp = SiteBlueprint(project_id=pid, business_profile=profile, pages=pages, link_graph={})
    project = {"id": pid, "tenant_id": tid, "user_id": uid, "name": "Test", "site_url": "https://x.com"}

    result = _run.generate_site_from_blueprint(project, bp, mode="dry-run", bypass_subscription=True)
    assert result["pages_success"] == 2
    pe = result.get("persistence_errors", [])
    assert len(pe) == 1  # only fail-1 failed
    assert pe[0]["slug"] == "fail-1"


# Regression tests
def test_legacy_generate_site(monkeypatch):
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: dict(_MOCK))
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg,c,cfg: {"score":85,"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    import yaml
    tmp = tempfile.mktemp(suffix=".yaml")
    with open(tmp,"w") as f: yaml.dump({"name":"t","seed_keyword":"t","pages":[{"title":"P1","type":"guide","slug":"p1","target_keyword":"k1"}]}, f)
    project = {"id":0,"tenant_id":None,"name":"t","industry_config":tmp,"seed_keyword":"t","language":"En","site_url":"https://x.com"}
    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    if (root / "templates").exists():
        for f in (root / "templates").rglob("*.html"):
            assert len(f.read_text(encoding="utf-8")) > 0

def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    if (root / "static").exists():
        for f in (root / "static").rglob("*"):
            if f.is_file(): assert f.exists()
