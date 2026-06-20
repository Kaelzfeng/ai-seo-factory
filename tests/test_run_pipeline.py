# -*- coding: utf-8 -*-
"""tests/test_run_pipeline.py · 生成管线集成测试

覆盖: LLM 重试、内容验证、CLI bypass subscription、Web 额度限制、错误诊断。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as _run
import models


# ── 辅助 ────────────────────────────────────────────

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

_EMPTY_CONTENT = {}


# ── _content_is_valid ────────────────────────────────


def test_content_is_valid_ok():
    assert _run._content_is_valid(_MOCK_CONTENT) == (True, "ok")


def test_content_is_valid_none():
    assert _run._content_is_valid(None) == (False, "LLM 返回 None")


def test_content_is_valid_empty_dict():
    assert _run._content_is_valid({}) == (False, "LLM 返回空 dict {}")


def test_content_is_valid_not_dict():
    assert _run._content_is_valid("string") == (False, "LLM 返回非 dict 类型: str")


def test_content_is_valid_missing_key():
    bad = {"title": "T", "meta_description": "M"}
    valid, reason = _run._content_is_valid(bad)
    assert valid is False
    assert "缺少必需字段" in reason
    assert "html" in reason


def test_content_is_valid_empty_value():
    bad = {"title": "", "meta_description": "M", "html": "H"}
    valid, reason = _run._content_is_valid(bad)
    assert valid is False
    assert "title" in reason


def test_content_is_valid_whitespace_only():
    bad = {"title": "   ", "meta_description": "M", "html": "H"}
    valid, reason = _run._content_is_valid(bad)
    assert valid is False


# ── _call_llm_with_retry (Phase 1.1: 4-tier) ────────

_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "meta_description": {"type": "string"}, "html": {"type": "string"}},
    "required": ["title", "meta_description", "html"],
}


def test_retry_succeeds_first_try(monkeypatch):
    """第一次调用就返回有效内容。"""
    calls = []
    def fake_structured(**kw):
        calls.append(1)
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert len(calls) == 1


def test_retry_succeeds_after_empty(monkeypatch):
    """第一次返回空,第二次成功(normal → retry)。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 2:
            return {}
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 2


def test_retry_succeeds_after_none(monkeypatch):
    """第一次返回 None,第二次成功。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 2:
            return None
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 2


def test_retry_succeeds_after_exception(monkeypatch):
    """第一次抛异常,第二次成功。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 2:
            raise RuntimeError("API error")
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 2


def test_retry_strict_json_succeeds(monkeypatch):
    """前 2 次空 dict,第 3 次 strict JSON reminder 成功。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 3:
            return {}
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 3  # normal + retry + strict


def test_retry_fallback_succeeds(monkeypatch):
    """前 3 次空 dict,第 4 次 fallback minimal prompt 成功。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 4:
            return {}
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="test", target_kw="kw",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 4  # all 4 tiers tried


def test_retry_exhausted_raises(monkeypatch):
    """4 次全部失败,抛出 RuntimeError with detail。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    with pytest.raises(RuntimeError, match="4 次尝试全部失败"):
        _run._call_llm_with_retry(
            system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
            page_label="doomed", page_type="guide", page_slug="doomed", target_kw="kw",
        )


def test_retry_exhausted_with_exception(monkeypatch):
    """全部重试都抛异常,抛出 RuntimeError。"""
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    with pytest.raises(RuntimeError, match="4 次尝试全部失败"):
        _run._call_llm_with_retry(
            system_prompt="sys", user_prompt="user", schema_def=_SCHEMA,
            page_label="doomed", page_type="guide", page_slug="doomed", target_kw="kw",
        )


# ── generate_site: CLI bypass subscription ───────────


def test_generate_site_bypass_subscription(monkeypatch):
    """bypass_subscription=True 时跳过额度检查,即使没有 tenant。"""
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
        "id": 0,
        "tenant_id": None,
        "user_id": None,
        "name": "test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test kw",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is True
    assert result["summary"]["total_pages"] == 8
    assert len(result["pages"]) == 8
    assert result["summary"]["subscription_check"] == {"bypassed": True}

    try:
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── generate_site: Web 用户受额度限制 ─────────────────


def test_generate_site_respects_subscription(monkeypatch):
    """有 tenant_id 且不 bypass 时,订阅额度检查生效。"""
    # 建立隔离 DB 并注入到 models._get_db
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("quota-tenant")
    models.create_subscription(tid, plan_code="free", status="active")
    # 用完 generation 额度
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
    assert len(result["errors"]) >= 1
    assert any("额度检查失败" in e or "generation_limit" in e for e in result["errors"])

    conn.close()
    try:
        os.unlink(dbpath)
    except OSError:
        pass


# ── generate_site: 页面失败返回明确错误 ───────────────


def test_generate_site_reports_failure_clearly(monkeypatch):
    """某页 LLM 全部重试失败后,result.errors 包含明确信息。"""
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 0})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    monkeypatch.setattr(_run, "_MAX_TOTAL_ATTEMPTS", 1)

    # 所有 LLM 调用都返回空
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "test", "seed_keyword": "test",
            "pages": [
                {"title": "Page 1", "type": "guide", "slug": "p1", "target_keyword": "k1"},
                {"title": "Page 2", "type": "guide", "slug": "p2", "target_keyword": "k2"},
            ],
        }, f)

    project = {
        "id": 0,
        "tenant_id": None,
        "user_id": None,
        "name": "fail-test",
        "industry_config": tmp_yaml,
        "seed_keyword": "test",
        "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is False
    assert result["summary"]["total_pages"] == 0
    assert result["code"] == "generation_failed"
    assert len(result["errors"]) >= 2
    for err in result["errors"]:
        assert "生成失败" in err

    try:
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── generate_site: partial success ───────────────────


def test_generate_site_partial_success(monkeypatch):
    """部分页成功、部分失败时,只记录成功的页。"""
    # 设置隔离 DB,让 failed_generation_ids 能写入
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    tid = models.create_tenant("partial-tenant")
    uid = models.create_user("partial@test.com", "h", "s")
    real_pid = models.create_project(
        user_id=uid, name="Partial Project", tenant_id=tid,
        seed_keyword="test", language="English", site_url="https://example.com",
    )

    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    # 禁用额外重试,让每页只试一次,便于控制成功/失败
    monkeypatch.setattr(_run, "_MAX_TOTAL_ATTEMPTS", 1)

    # 预定义每页返回值:第 1 页成功,第 2 页失败,第 3 页成功,第 4 页失败
    responses = [_MOCK_CONTENT, {}, _MOCK_CONTENT, {}]
    call_idx = [-1]

    def fake_structured(**kw):
        call_idx[0] += 1
        resp = responses[call_idx[0]]
        if isinstance(resp, dict) and resp:
            return resp
        if not resp:  # 空 dict
            return {}
        raise RuntimeError("simulated API failure")

    monkeypatch.setattr(_run.llm, "structured", fake_structured)

    # 写临时 YAML 配置文件,确保 industry_config_path 有效
    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "test", "seed_keyword": "test",
            "pages": [
                {"title": f"P{n}", "type": "guide", "slug": f"p{n}", "target_keyword": f"k{n}"}
                for n in range(1, 5)
            ],
        }, f)

    project = {
        "id": real_pid, "tenant_id": None, "user_id": None,
        "name": "partial", "industry_config": tmp_yaml,
        "seed_keyword": "test", "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    # 4 页中 2 成功 2 失败 → partial_success
    assert result["summary"]["total_pages"] == 2
    assert len(result["errors"]) == 2
    assert result["ok"] is False
    assert result["code"] == "partial_success"
    assert result["retryable"] is True
    assert len(result["failed_generation_ids"]) == 2

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass
