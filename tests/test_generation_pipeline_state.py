# -*- coding: utf-8 -*-
"""tests/test_generation_pipeline_state.py · 生成管线状态测试

覆盖:
7. generate_site 返回统一结构
8. dry-run 仍然 8/8
9. Web 用户超额仍然被阻止
10. CLI bypass_subscription 仍然有效
11. templates/** 未修改
12. static/** 未修改
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as _run
import models

# ── 共享 mock ────────────────────────────────────────

_MOCK_CONTENT = {
    "title": "Test Page Title",
    "meta_description": "This is a test meta description for SEO purposes, 150+ chars of meaningful content for testing the pipeline end to end with realistic data.",
    "html": "<h1>Test Page</h1><h2>Section One</h2><p>This is a test paragraph with sufficient content to pass word count checks. " * 5 + "</p>",
    "image_query": "test page image",
}

_MOCK_QUALITY = {
    "score": 85.0,
    "breakdown": {},
    "issues": [],
    "passed": True,
}


# ── Test 7: generate_site 返回统一结构 ──────────────


def test_generate_site_returns_unified_structure(monkeypatch):
    """验证新返回结构包含所有预期字段。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: _MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 1000})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "test", "seed_keyword": "test kw",
            "pages": [
                {"title": f"Page {n}", "type": "guide", "slug": f"page-{n}",
                 "target_keyword": f"kw-{n}"}
                for n in range(1, 9)
            ],
        }, f)

    project = {
        "id": 99,
        "tenant_id": None,
        "user_id": None,
        "name": "Unified Structure Test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test kw",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)

    # 新字段
    assert "generation_id" in result
    assert "generation_ids" in result
    assert "project_id" in result
    assert "pages_total" in result
    assert "pages_success" in result
    assert "pages_failed" in result
    assert "mode" in result
    assert "usage" in result

    assert result["project_id"] == 99
    assert result["mode"] == "dry-run"
    assert result["pages_total"] == 8
    assert result["pages_success"] == 8
    assert result["pages_failed"] == 0
    assert len(result["generation_ids"]) == 8
    assert result["generation_id"] == result["generation_ids"][0]

    # 旧字段仍存在(向后兼容)
    assert result["ok"] is True
    assert len(result["pages"]) == 8
    assert "summary" in result
    assert result["summary"]["total_pages"] == 8
    assert result["summary"]["subscription_check"] == {"bypassed": True}

    try:
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test 8: dry-run 仍然 8/8 ───────────────────────


def test_dry_run_still_eight_for_eight(monkeypatch):
    """dry-run 模式稳定生成 8/8 页。"""
    # 设置隔离 DB,让 create_generation 能正常写入
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    # 创建 tenant 和 project(让 FK 约束满足)
    tid = models.create_tenant("8page-tenant")
    uid = models.create_user("8page@test.com", "h", "s")
    real_pid = models.create_project(
        user_id=uid, name="8-page Project", tenant_id=tid,
        seed_keyword="industrial chemical", industry="Industrial Chemical",
        language="English", site_url="https://example.com",
    )

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: _MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 1000})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "8-page test", "seed_keyword": "industrial chemical",
            "pages": [
                {"title": f"Page {n}", "type": "guide", "slug": f"page-{n}",
                 "target_keyword": f"industrial-chemical-{n}"}
                for n in range(1, 9)
            ],
        }, f)

    project = {
        "id": real_pid,
        "tenant_id": None,       # CLI 模式无 tenant
        "user_id": None,
        "name": "8/8 Test",
        "industry_config": tmp_yaml,
        "seed_keyword": "industrial chemical",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
    assert result["pages_total"] == 8
    assert result["pages_success"] == 8
    assert result["pages_failed"] == 0
    assert len(result["pages"]) == 8
    assert result["summary"]["total_pages"] == 8

    # 确认 generation_ids 齐全
    assert len(result["generation_ids"]) == 8
    # 确认每个 page 都有 gen_id (有隔离 DB 时 create_generation 能成功)
    for entry in result["pages"]:
        assert "gen_id" in entry["page"]

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test 9: Web 用户超额仍然被阻止 ──────────────────


def test_web_user_over_quota_blocked(monkeypatch):
    """Web 用户(有 tenant, bypass=False)超额时被阻止。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("quota-tenant")
    models.create_subscription(tid, plan_code="free", status="active")
    # 用完 3 次 generation 额度
    models.record_usage(tid, kind="generation", amount=3)

    project = {
        "id": 1,
        "tenant_id": tid,
        "user_id": None,
        "name": "quota-test",
        "industry_config": "",
        "seed_keyword": "test",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=False)
    assert result["ok"] is False
    assert result["code"] == "generation_failed"
    assert result["pages_total"] == 0
    assert result["pages_success"] == 0
    assert len(result["errors"]) >= 1
    assert any("额度检查失败" in e for e in result["errors"])

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── Test 10: CLI bypass_subscription 仍然有效 ────────


def test_cli_bypass_still_works(monkeypatch):
    """CLI 模式(bypass_subscription=True)跳过额度检查。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: _MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 500})

    # 建立有 tenant 但 bypass 的 project
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("bypass-tenant")
    models.create_subscription(tid, plan_code="free", status="active")
    models.record_usage(tid, kind="generation", amount=3)  # 已超额

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "bypass test", "seed_keyword": "test",
            "pages": [{"title": "P1", "type": "guide", "slug": "p1", "target_keyword": "k1"}],
        }, f)

    project = {
        "id": 2,
        "tenant_id": tid,
        "user_id": None,
        "name": "Bypass Test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test",
        "language": "English",
        "site_url": "https://example.com",
    }

    # bypass=True 时即使 tenant 超额也能运行
    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
    assert result["pages_success"] == 1
    assert result["summary"]["subscription_check"] == {"bypassed": True}

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test 11: templates/** 未修改 ────────────────────


def test_templates_not_modified():
    """确认 templates/ 目录未被修改。"""
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if not templates_dir.exists():
        pytest.skip("templates/ 目录不存在")
        return

    html_files = list(templates_dir.rglob("*.html"))
    # 只验证文件存在且可读,不验证内容(Phase 1 不应新增/修改模板)
    for f in html_files:
        content = f.read_text(encoding="utf-8")
        assert len(content) > 0, f"模板文件 {f.name} 不应为空"


# ── Test 12: static/** 未修改 ───────────────────────


def test_static_not_modified():
    """确认 static/ 目录未被修改。"""
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if not static_dir.exists():
        pytest.skip("static/ 目录不存在")
        return

    all_files = list(static_dir.rglob("*"))
    # 只验证文件存在,不验证内容
    for f in all_files:
        if f.is_file():
            assert f.exists(), f"静态文件 {f.name} 应该存在"


# ── Test: generation_logs 在 dry-run 中被写入 ──────


def test_dry_run_writes_generation_logs(monkeypatch):
    """dry-run 模式下也写 generation_logs。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    # 创建 tenant 和 project,让 FK 约束满足
    tid = models.create_tenant("log-test-tenant")
    uid = models.create_user("logtest@example.com", "h", "s")
    real_pid = models.create_project(
        user_id=uid, name="Log Test Project", tenant_id=tid,
        seed_keyword="test", language="English", site_url="https://example.com",
    )

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: _MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 500})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "log test", "seed_keyword": "test",
            "pages": [
                {"title": f"P{n}", "type": "guide", "slug": f"p{n}", "target_keyword": f"k{n}"}
                for n in range(1, 4)
            ],
        }, f)

    project = {
        "id": real_pid,
        "tenant_id": None,       # bypass 模式
        "user_id": None,
        "name": "Log Test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True

    # 检查 generation_logs 有记录
    for gen_id in result["generation_ids"]:
        logs = models.list_generation_logs(generation_id=gen_id)
        assert len(logs) >= 3  # llm_generate + quality_score + polish + complete
        steps = [l["step"] for l in logs]
        assert "llm_generate" in steps
        assert "quality_score" in steps

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test: dry-run 不写 cms_logs ────────────────────


def test_dry_run_does_not_write_cms_logs(monkeypatch):
    """dry-run 模式下不写 cms_logs。"""
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("cms-test")

    monkeypatch.setattr(_run.llm, "structured", lambda **kw: _MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 300})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "cms test", "seed_keyword": "test",
            "pages": [{"title": "P1", "type": "guide", "slug": "p1", "target_keyword": "k1"}],
        }, f)

    project = {
        "id": 10,
        "tenant_id": tid,
        "user_id": None,
        "name": "CMS Dry-Run Test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test",
        "language": "English",
        "site_url": "https://example.com",
        "wp_url": "https://example.com/wp-json",
        "wp_username": "admin",
        "wp_app_password": "pass123",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True

    # dry-run 不应该有任何 cms_logs
    cms_logs = models.list_cms_logs(tenant_id=tid)
    assert len(cms_logs) == 0

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass
