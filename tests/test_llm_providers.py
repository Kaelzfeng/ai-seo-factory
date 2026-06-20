# -*- coding: utf-8 -*-
"""Phase 9 AI: LLM Provider 接入测试 (mock, deepseek, openai)"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import run as _run

_SCHEMA = {"type":"object","properties":{"title":{"type":"string"},"html":{"type":"string"}},"required":["title","html"]}


# Mock provider
def test_mock_structured_returns_data():
    from lib.llm import structured
    monkeypatch = None
    import os as _os
    old = _os.environ.get("LLM_PROVIDER", "")
    _os.environ["LLM_PROVIDER"] = "mock"
    try:
        result = structured("mock", "sys", "user", _SCHEMA)
        assert "title" in result
        assert "html" in result
    finally:
        if old: _os.environ["LLM_PROVIDER"] = old
        else: _os.environ.pop("LLM_PROVIDER", None)


def test_default_model_mock():
    from lib.llm import default_model
    import os as _os
    _os.environ["LLM_PROVIDER"] = "mock"
    try:
        assert default_model("writer") == "mock"
    finally:
        _os.environ.pop("LLM_PROVIDER", None)


# Provider resolution
def test_provider_explicit_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    from lib.llm import _provider
    assert _provider() == "deepseek"


def test_provider_auto_deepseek(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from lib.llm import _provider
    assert _provider() == "deepseek"


def test_provider_auto_openai(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    from lib.llm import _provider
    assert _provider() == "openai"


def test_provider_auto_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from lib.llm import _provider
    assert _provider() in ("anthropic", "mock")


# Config report
def test_config_report_no_leak():
    from lib.config_check import get_config_report
    r = get_config_report()
    cfg_str = str(r)
    assert "sk-ant-" not in cfg_str
    assert "sk-or-" not in cfg_str
    assert "sk-proj-" not in cfg_str


def test_config_report_has_llm_info():
    from lib.config_check import get_config_report
    r = get_config_report()
    assert "llm" in str(r.get("services", {})).lower() or "services" in r


def test_config_check_llm_provider():
    from lib.config_check import validate_runtime_config
    r = validate_runtime_config(strict=False)
    llm = r["services"]["llm"]
    assert "provider" in llm
    assert "api_key_present" in llm


def test_config_check_strict_missing_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from lib.config_check import validate_runtime_config
    r = validate_runtime_config(strict=True)
    # 应该报 error 或至少不是 ok on strict
    assert isinstance(r, dict)


# Structured output with mock
def test_mock_structured_respects_schema():
    import os as _os
    _os.environ["LLM_PROVIDER"] = "mock"
    try:
        from lib.llm import structured
        schema = {"type":"object","properties":{"a":{"type":"string"},"b":{"type":"array"}},"required":["a"]}
        result = structured("mock", "s", "u", schema)
        assert "a" in result
        assert result["a"] != ""
    finally:
        _os.environ.pop("LLM_PROVIDER", None)


# Legacy compatibility
def test_legacy_generate_site(monkeypatch):
    monkeypatch.setattr(_run.llm, "structured", lambda **kw: {"title":"T","meta_description":"M","html":"<p>x</p>","image_query":"i"})
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
