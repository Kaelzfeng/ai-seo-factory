# -*- coding: utf-8 -*-
"""tests/test_auth_tenant.py · 用户注册 → tenant → 订阅自动绑定测试"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models
import auth
from lib.subscription import check_generation_allowed, get_subscription_status
from lib.usage import get_usage_summary


import pytest


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
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


# ── 密码学 ──────────────────────────────────────────


def test_hash_and_verify_password():
    """PBKDF2-HMAC-SHA256 哈希+验证正确。"""
    pw_hash, pw_salt = auth.hash_password("my-secure-password")
    assert len(pw_hash) == 64  # sha256 hex = 64 chars
    assert len(pw_salt) == 64  # 32 bytes hex = 64 chars
    assert auth.verify_password("my-secure-password", pw_salt, pw_hash) is True
    assert auth.verify_password("wrong-password", pw_salt, pw_hash) is False


def test_hash_password_random_salt():
    """每次调用 hash_password 生成不同的 salt。"""
    _, salt1 = auth.hash_password("test")
    _, salt2 = auth.hash_password("test")
    assert salt1 != salt2


def test_hash_password_with_given_salt():
    """传入已知 salt 可以复现相同 hash。"""
    pw_hash1, salt = auth.hash_password("test")
    pw_hash2, _ = auth.hash_password("test", salt=salt)
    assert pw_hash1 == pw_hash2


def test_verify_password_empty_salt():
    """空 salt 时验证失败(不崩溃)。"""
    assert auth.verify_password("test", "", "somehash") is False


# ── 注册自动创建 Tenant + Subscription ─────────────


def test_register_creates_user():
    """注册创建用户记录。"""
    result = auth.register_user("demo@example.com", "secure123")
    user = result["user"]
    assert user["email"] == "demo@example.com"
    assert user["password_hash"] != "secure123"
    assert len(user["password_salt"]) > 0


def test_register_creates_tenant():
    """注册自动创建 tenant。"""
    result = auth.register_user("tenant-test@example.com", "secure123")
    tenant = result["tenant"]
    assert tenant is not None
    assert tenant["name"] is not None
    assert len(tenant["name"]) > 0


def test_register_creates_tenant_member():
    """注册自动创建 tenant_member 关联。"""
    result = auth.register_user("member-test@example.com", "secure123")
    user = result["user"]
    tenant = result["tenant"]
    member = models.get_tenant_member(tenant["id"], user["id"])
    assert member is not None
    assert member["role"] == "owner"


def test_register_binds_free_subscription():
    """注册自动绑定 Free 订阅。"""
    result = auth.register_user("sub-test@example.com", "secure123")
    tenant = result["tenant"]
    assert result["subscription"] == "free"
    # 确认可以生成
    check = check_generation_allowed(tenant["id"])
    assert check["allowed"] is True
    assert check["subscription"]["plan_code"] == "free"


def test_register_duplicate_email_raises():
    """重复邮箱注册抛 ValueError。"""
    auth.register_user("dup@example.com", "pass123")
    with pytest.raises(ValueError, match="已注册"):
        auth.register_user("dup@example.com", "pass456")


def test_register_free_plan_quota_correct():
    """新注册用户的 Free 额度为 3 次生成 / 100k token。"""
    result = auth.register_user("quota@example.com", "secure123")
    tid = result["tenant"]["id"]
    status = get_subscription_status(tid)
    assert status["plan"]["monthly_generation_limit"] == 3
    assert status["plan"]["monthly_token_limit"] == 100000


# ── 认证 ───────────────────────────────────────────


def test_authenticate_success():
    """正确密码认证成功。"""
    auth.register_user("auth-test@example.com", "mypassword")
    user = auth.authenticate_user("auth-test@example.com", "mypassword")
    assert user is not None
    assert user["email"] == "auth-test@example.com"


def test_authenticate_wrong_password():
    """错误密码返回 None。"""
    auth.register_user("wrong-pass@example.com", "correct")
    assert auth.authenticate_user("wrong-pass@example.com", "wrong") is None


def test_authenticate_nonexistent_user():
    """不存在的用户返回 None。"""
    assert auth.authenticate_user("nobody@example.com", "pass") is None


# ── 超额阻断端到端 ─────────────────────────────────


def test_generation_blocked_after_quota_exceeded():
    """注册后用完 Free 额度,第 4 次被阻止。"""
    result = auth.register_user("quota-exceed@example.com", "pass123")
    tid = result["tenant"]["id"]
    uid = result["user"]["id"]

    # 3 次生成后应达到上限
    models.record_usage(tid, user_id=uid, kind="generation", amount=3)
    check = check_generation_allowed(tid)
    assert check["allowed"] is False
    assert check["code"] == "generation_limit_reached"


def test_usage_summary_after_registration():
    """新注册用户 usage 初始为 0。"""
    result = auth.register_user("fresh-usage@example.com", "pass123")
    tid = result["tenant"]["id"]
    summary = get_usage_summary(tid)
    assert summary["generations"] == 0
    assert summary["tokens"] == 0


def test_subscription_status_api_shape():
    """get_subscription_status 返回正确的 JSON 结构。"""
    result = auth.register_user("api-shape@example.com", "pass123")
    tid = result["tenant"]["id"]
    status = get_subscription_status(tid)
    assert "subscription" in status
    assert "plan" in status
    assert "usage" in status
    assert status["subscription"]["plan_code"] == "free"
    assert status["subscription"]["status"] == "active"
