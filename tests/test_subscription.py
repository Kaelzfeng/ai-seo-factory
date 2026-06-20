# -*- coding: utf-8 -*-
"""tests/test_subscription.py · 订阅逻辑测试"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 临时数据库隔离
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models
from lib.subscription import (
    check_generation_allowed,
    get_subscription_status,
    create_free_subscription,
    ensure_default_plans,
    is_subscription_active,
)


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """每个测试用独立临时 DB,互不污染。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = models.init_db(path)
    monkeypatch.setattr(models, "_get_db", lambda: conn)
    yield
    conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


def test_ensure_default_plans_creates_free():
    """首次初始化后 free 套餐存在且额度正确。"""
    ensure_default_plans()
    plan = models.get_plan("free")
    assert plan is not None
    assert plan["code"] == "free"
    assert plan["name"] == "Free"
    assert plan["monthly_generation_limit"] == 3
    assert plan["monthly_token_limit"] == 100000
    assert plan["max_projects"] == 1
    assert plan["max_sites"] == 1
    assert plan["competitor_analysis_limit"] == 1
    assert plan["price_cents"] == 0


def test_create_free_subscription():
    """为新 tenant 创建 Free 订阅后状态为 active。"""
    tid = models.create_tenant("test-co")
    sub_id = create_free_subscription(tid)
    assert sub_id > 0
    sub = models.get_active_subscription(tid)
    assert sub is not None
    assert sub["plan_code"] == "free"
    assert sub["status"] == "active"


def test_is_subscription_active_returns_true():
    """刚创建的 Free 订阅应活跃。"""
    tid = models.create_tenant("active-co")
    create_free_subscription(tid)
    assert is_subscription_active(tid) is True


def test_check_generation_allowed_new_tenant():
    """新 tenant 自动获得 Free 订阅,允许生成。"""
    tid = models.create_tenant("fresh-co")
    # 不手动创建订阅:check 内部自动纠错
    result = check_generation_allowed(tid)
    assert result["allowed"] is True
    assert result["subscription"]["plan_code"] == "free"
    assert result["subscription"]["generations_limit"] == 3


def test_check_generation_allowed_after_limit():
    """超过 generation 限制后阻止生成。"""
    tid = models.create_tenant("limit-co")
    create_free_subscription(tid)
    # 模拟已用 3 次 generation
    models.record_usage(tid, kind="generation", amount=3)
    result = check_generation_allowed(tid)
    assert result["allowed"] is False
    assert result["code"] == "generation_limit_reached"
    assert "3/3" in result["reason"]


def test_check_generation_allowed_expired_subscription(monkeypatch):
    """过期订阅阻止生成。"""
    import time
    tid = models.create_tenant("expired-co")
    models.create_subscription(tid, plan_code="free", status="active",
                               expire_at="2020-01-01T00:00:00")
    # 确认被识别为过期
    result = check_generation_allowed(tid)
    assert result["allowed"] is False
    assert result["code"] == "subscription_expired"


def test_get_subscription_status():
    """返回完整订阅状态(含 usage)。"""
    tid = models.create_tenant("status-co")
    create_free_subscription(tid)
    models.record_usage(tid, kind="generation", amount=1)
    models.record_usage(tid, kind="token", amount=5000)

    status = get_subscription_status(tid)
    assert status["subscription"] is not None
    assert status["subscription"]["plan_code"] == "free"
    assert status["subscription"]["status"] == "active"
    assert status["plan"]["name"] == "Free"
    assert status["plan"]["monthly_generation_limit"] == 3
    assert status["usage"]["generation"] == 1
    assert status["usage"]["token"] == 5000


def test_token_limit_also_blocks():
    """超过 token 限制也阻止生成。"""
    tid = models.create_tenant("token-limit-co")
    create_free_subscription(tid)
    models.record_usage(tid, kind="token", amount=100000)
    result = check_generation_allowed(tid)
    assert result["allowed"] is False
    assert result["code"] == "token_limit_reached"


def test_inactive_subscription_blocks():
    """status 非 active 时阻止生成。"""
    tid = models.create_tenant("inactive-co")
    models.create_subscription(tid, plan_code="free", status="canceled")
    result = check_generation_allowed(tid)
    assert result["allowed"] is False
    assert result["code"] == "subscription_inactive"
