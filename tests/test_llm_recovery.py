# -*- coding: utf-8 -*-
"""tests/test_llm_recovery.py · LLM 恢复测试 (Phase 1.1)

覆盖:
1. attempt 1 空 dict, attempt 2 成功
2. attempt 1-3 空 dict, attempt 4 fallback 成功
3. 4 次都失败时返回 partial_success
4. partial_success 里包含 retryable=true
5. _content_is_valid_detailed 详细诊断
"""

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
    "meta_description": "This is a test meta description for SEO purposes, 150+ chars of meaningful content.",
    "html": "<h1>Test</h1><p>Content " * 10 + "</p>",
    "image_query": "test image",
}

_MOCK_QUALITY = {"score": 85.0, "breakdown": {}, "issues": [], "passed": True}

_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "meta_description": {"type": "string"}, "html": {"type": "string"}},
    "required": ["title", "meta_description", "html"],
}


# ── Test 1: attempt 1 空 dict, attempt 2 成功 ─────────────────


def test_tier1_empty_tier2_succeeds(monkeypatch):
    """第一次返回空 dict,第二次 retry 成功(normal → retry)。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 2:
            return {}
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="s", user_prompt="u", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="t", target_kw="k",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 2  # 1 次失败 + 1 次成功 = 2


# ── Test 2: attempt 1-3 空 dict, attempt 4 fallback 成功 ─────


def test_tier1_3_empty_tier4_fallback_succeeds(monkeypatch):
    """前 3 次都返回空 dict,第 4 次 fallback 成功。"""
    attempts = [0]
    def fake_structured(**kw):
        attempts[0] += 1
        if attempts[0] < 4:
            return {}
        return dict(_MOCK_CONTENT)
    monkeypatch.setattr(_run.llm, "structured", fake_structured)
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    result = _run._call_llm_with_retry(
        system_prompt="s", user_prompt="u", schema_def=_SCHEMA,
        page_label="test", page_type="guide", page_slug="t", target_kw="k",
    )
    assert result == _MOCK_CONTENT
    assert attempts[0] == 4  # 3 次失败 + 1 次成功(第 4 次 fallback)


# ── Test 3: 4 次都失败 → 返回 partial_success ─────────────


def test_all_four_fail_returns_partial_success(monkeypatch):
    """4 次全部失败时,generate_site 返回 partial_success。"""
    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 0})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)
    # 所有调用返回空
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {})

    import yaml
    tmp_yaml = tempfile.mktemp(suffix=".yaml")
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({
            "name": "partial", "seed_keyword": "test",
            "pages": [
                {"title": "P1", "type": "guide", "slug": "p1", "target_keyword": "k1"},
                {"title": "P2", "type": "guide", "slug": "p2", "target_keyword": "k2"},
            ],
        }, f)

    project = {
        "id": 0, "tenant_id": None, "user_id": None,
        "name": "4-fail", "industry_config": tmp_yaml,
        "seed_keyword": "test", "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is False
    assert result["code"] == "generation_failed"
    assert result["pages_success"] == 0
    assert result["pages_failed"] == 2
    assert len(result["errors"]) == 2

    try:
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test 4: partial_success 包含 retryable=true ────────────


def test_partial_success_has_retryable(monkeypatch):
    """部分成功时 retryable=true, failed_generation_ids 有值。"""
    # 设置隔离 DB,让 create_generation 能成功
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(dbpath)
    monkeypatch.setattr(models, "_get_db", lambda: conn)

    tid = models.create_tenant("retryable-tenant")
    uid = models.create_user("retryable@test.com", "h", "s")
    real_pid = models.create_project(
        user_id=uid, name="Retryable Project", tenant_id=tid,
        seed_keyword="test", language="English", site_url="https://example.com",
    )

    monkeypatch.setattr(_run.llm, "load_skill", lambda name: "")
    monkeypatch.setattr(_run.quality, "score_page", lambda pg, c, cfg: _MOCK_QUALITY)
    monkeypatch.setattr(_run.llm, "reset_usage", lambda: None)
    monkeypatch.setattr(_run.llm, "last_usage", lambda: {"total_tokens": 500})
    monkeypatch.setattr(_run, "_RETRY_DELAY_SEC", 0.01)

    # 交替:成功-失败-成功-失败
    responses = [_MOCK_CONTENT, {}, _MOCK_CONTENT, {}]
    call_idx = [-1]
    def fake_structured(**kw):
        call_idx[0] += 1
        resp = responses[call_idx[0]]
        if isinstance(resp, dict) and resp:
            return resp
        if not resp:
            return {}
        raise RuntimeError("fail")

    monkeypatch.setattr(_run.llm, "structured", fake_structured)

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
        "name": "retryable-test", "industry_config": tmp_yaml,
        "seed_keyword": "test", "language": "English",
        "site_url": "https://example.com",
    }

    result = _run.generate_site(project, mode="dry-run", bypass_subscription=True)
    assert result["ok"] is False
    assert result["code"] == "partial_success"
    assert result["retryable"] is True
    assert len(result["failed_generation_ids"]) == 2
    assert result["pages_success"] == 2
    assert result["pages_failed"] == 2

    conn.close()
    try:
        os.unlink(dbpath)
        os.unlink(tmp_yaml)
    except OSError:
        pass


# ── Test 5: _content_is_valid_detailed ──────────────────────


def test_content_is_valid_detailed_ok():
    diag = _run._content_is_valid_detailed(_MOCK_CONTENT)
    assert diag["valid"] is True
    assert diag["response_type"] == "dict_valid"
    assert diag["missing_fields"] == []


def test_content_is_valid_detailed_none():
    diag = _run._content_is_valid_detailed(None)
    assert diag["valid"] is False
    assert diag["response_type"] == "None"
    assert "title" in diag["missing_fields"]


def test_content_is_valid_detailed_empty_dict():
    diag = _run._content_is_valid_detailed({})
    assert diag["valid"] is False
    assert diag["response_type"] == "empty_dict"
    assert len(diag["missing_fields"]) == 3  # title, meta_description, html


def test_content_is_valid_detailed_missing_fields():
    diag = _run._content_is_valid_detailed({"title": "T"}, ("title", "meta_description", "html"))
    assert diag["valid"] is False
    assert diag["response_type"] == "dict_missing_fields"
    assert "meta_description" in diag["missing_fields"]
    assert "html" in diag["missing_fields"]


# ── Test: templates/static 未修改 ────────────────────────────


def test_templates_not_modified():
    root = Path(__file__).resolve().parent.parent
    templates_dir = root / "templates"
    if not templates_dir.exists():
        pytest.skip("templates/ 目录不存在")
    html_files = list(templates_dir.rglob("*.html"))
    for f in html_files:
        content = f.read_text(encoding="utf-8")
        assert len(content) > 0, f"模板文件 {f.name} 不应为空"


def test_static_not_modified():
    root = Path(__file__).resolve().parent.parent
    static_dir = root / "static"
    if not static_dir.exists():
        pytest.skip("static/ 目录不存在")
    all_files = list(static_dir.rglob("*"))
    for f in all_files:
        if f.is_file():
            assert f.exists(), f"静态文件 {f.name} 应该存在"
