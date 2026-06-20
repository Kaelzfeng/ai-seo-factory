# -*- coding: utf-8 -*-
"""provider 自动识别 + 角色默认模型(纯函数,无网络)。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import llm


def test_provider_defaults_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert llm._provider() == "anthropic"


def test_provider_autodetect_deepseek_from_key(monkeypatch):
    # 只要设了 DEEPSEEK_API_KEY,不写 LLM_PROVIDER 也自动走 deepseek
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert llm._provider() == "deepseek"


def test_provider_explicit_overrides_key(monkeypatch):
    # 显式 LLM_PROVIDER 优先于自动识别
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert llm._provider() == "anthropic"


def test_default_model_per_provider():
    assert llm.default_model("planner", "deepseek") == "deepseek-v4-flash"
    assert llm.default_model("writer", "deepseek") == "deepseek-v4-pro"
    assert llm.default_model("planner", "anthropic") == "claude-haiku-4-5-20251001"
    assert llm.default_model("writer", "anthropic") == "claude-sonnet-4-6"
    # 未知 provider 回退 anthropic 默认
    assert llm.default_model("writer", "unknown") == "claude-sonnet-4-6"


def test_default_model_polish_role():
    assert llm.default_model("polish", "deepseek") == "deepseek-v4-flash"
    assert llm.default_model("polish", "anthropic") == "claude-haiku-4-5-20251001"
