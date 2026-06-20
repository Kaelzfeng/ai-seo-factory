# -*- coding: utf-8 -*-
"""Phase 5.1: 竞品 → Blueprint 全链路测试"""

import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import models


@pytest.fixture
def db():
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    yield conn
    conn.close()
    try: os.unlink(dbpath)
    except OSError: pass


def test_generate_blueprint_with_competitor_input(monkeypatch, db):
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("cbp-test")
    uid = models.create_user("cbp@test.com", "h", "s")
    pid = models.create_project(user_id=uid, name="CBP", tenant_id=tid, seed_keyword="test", language="English", site_url="https://x.com")

    import run as _run
    result = _run.generate_blueprint_with_competitor_input(
        user_input="I want an English B2B export site for PU leather",
        query="PU leather supplier", project_id=pid, tenant_id=tid,
    )
    assert result["ok"] is True
    assert result.get("competitor_report_id") is not None or result.get("hints_applied")
    assert result["pages_total"] >= 1
    assert result["hints_applied"] is True


def test_competitor_hints_merged_into_blueprint(monkeypatch, db):
    """hints 推荐页面合并后 slug 唯一且无 risk。"""
    monkeypatch.setattr(models, "_get_db", lambda: db)
    tid = models.create_tenant("merge-test")

    from lib.seo_engine.schemas import BusinessProfile
    from lib.seo_engine.stage2_blueprint import build_site_blueprint
    from lib.surpass_strategy import strategy_to_blueprint_hints, SurpassStrategy

    ss = SurpassStrategy(
        target_keyword="PU leather", recommended_pages=[
            "pu-leather-supplier", "pu-leather-vs-pvc", "pu-leather-for-furniture",
        ],
        recommended_sections=["Certifications", "MOQ guide"],
        recommended_faq=["What is MOQ?"],
    )
    hints = strategy_to_blueprint_hints(ss)

    profile = BusinessProfile(industry="PU leather", languages=["English"], target_markets=["global"], products=["PU leather"])
    bp = build_site_blueprint(project_id=1, profile=profile, competitor_hints=hints)

    # slug 唯一
    slugs = [p.slug for p in bp.pages]
    assert len(slugs) == len(set(slugs))

    # 无 fact risk
    for p in bp.pages:
        assert "is-real-leather" not in p.slug

    # link_graph 无孤儿
    linked = set()
    for src, targets in bp.link_graph.items():
        for t in targets:
            linked.add(t)
    for p in bp.pages:
        assert p.slug in linked or p.page_type == "guide"


def test_hints_inject_into_pageplan_fields(monkeypatch, db):
    """hints 注入后 PagePlan 有 competitor_gap_hints / recommended_faq / content_angle。"""
    monkeypatch.setattr(models, "_get_db", lambda: db)

    from lib.seo_engine.schemas import BusinessProfile
    from lib.seo_engine.stage2_blueprint import build_site_blueprint
    from lib.surpass_strategy import strategy_to_blueprint_hints, SurpassStrategy

    ss = SurpassStrategy(
        target_keyword="test",
        recommended_sections=["Sec1", "Sec2"],
        recommended_faq=["Q1"],
        recommended_schema=["Schema1"],
        content_angle="Test angle",
        differentiation_points=["Diff1"],
    )
    hints = strategy_to_blueprint_hints(ss)

    profile = BusinessProfile(industry="Test", languages=["English"], target_markets=["global"], products=["Test"])
    bp = build_site_blueprint(project_id=1, profile=profile, competitor_hints=hints)

    guide = next((p for p in bp.pages if p.page_type == "guide"), bp.pages[0])
    assert len(guide.competitor_gap_hints) > 0
    assert len(guide.recommended_faq) > 0
    assert guide.content_angle != ""


def test_legacy_still_works(monkeypatch):
    import run as _run
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"i"})
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg,c,cfg: {"score":85,"breakdown":{},"issues":[],"passed":True})
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens":500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({"name":"t","seed_keyword":"t","pages":[{"title":"P1","type":"guide","slug":"p1","target_keyword":"k1"}]}, f)
    project = {"id":0,"tenant_id":None,"user_id":None,"name":"t","industry_config":tmp_yaml,"seed_keyword":"t","language":"English","site_url":"https://x.com"}
    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
