# -*- coding: utf-8 -*-
"""auth.py · PBKDF2-HMAC-SHA256 + Flask session 登录

注册时自动创建 tenant / tenant_member / Free subscription。
"""

import hashlib
import os
import secrets
from functools import wraps

from flask import session, redirect, url_for, request
from models import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    create_tenant,
    add_tenant_member,
    get_tenant_member,
)
from lib.subscription import create_free_subscription


# ── 密码学 ──────────────────────────────────────────

_SALT_BYTES = 32
_HASH_ITERATIONS = 600_000
_HASH_NAME = "sha256"


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """PBKDF2-HMAC-SHA256 哈希密码。

    Args:
        password: 明文密码
        salt: 可选 hex salt;不传则生成随机 salt

    Returns:
        (password_hash_hex, salt_hex)
    """
    if salt is None:
        salt_bytes = os.urandom(_SALT_BYTES)
        salt = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)

    dk = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        password.encode("utf-8"),
        salt_bytes,
        _HASH_ITERATIONS,
    )
    return dk.hex(), salt


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """验证密码是否匹配。

    Args:
        password: 明文密码
        salt: 存储的 hex salt
        password_hash: 存储的 hex hash

    Returns:
        True 如果匹配
    """
    if not salt or not password_hash:
        return False
    computed, _ = hash_password(password, salt)
    return secrets.compare_digest(computed, password_hash)


# ── 用户操作 ────────────────────────────────────────


def register_user(email: str, password: str) -> dict:
    """注册新用户:创建 user → tenant → tenant_member → Free subscription。

    Returns:
        {"user": {...}, "tenant": {...}, "subscription": "free"}
    """
    from models import get_tenant

    # 检查重复
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("该邮箱已注册。")

    # 哈希密码
    pw_hash, pw_salt = hash_password(password)

    # 创建用户
    user_id = create_user(email, pw_hash, pw_salt)

    # 创建 tenant(以用户邮箱前缀命名)
    tenant_name = email.split("@")[0]
    tenant_id = create_tenant(tenant_name)

    # 关联 tenant_member
    add_tenant_member(tenant_id, user_id, role="owner")

    # 绑定 Free 订阅
    create_free_subscription(tenant_id)

    user = get_user_by_id(user_id)
    tenant = get_tenant(tenant_id)

    return {
        "user": user,
        "tenant": tenant,
        "subscription": "free",
    }


def authenticate_user(email: str, password: str) -> dict | None:
    """验证用户凭证,成功返回 user dict,失败返回 None。"""
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password,
                           user.get("password_salt", ""),
                           user.get("password_hash", "")):
        return None
    return user


# ── 会话 ────────────────────────────────────────────


def login_user(user: dict):
    """将用户 ID 写入 session。"""
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True


def logout_user():
    """清除 session。"""
    session.clear()


def current_user() -> dict | None:
    """获取当前登录用户(dict),未登录返回 None。"""
    uid = session.get("user_id")
    if not uid:
        return None
    return get_user_by_id(int(uid))


def current_tenant_id() -> int | None:
    """获取当前用户的第一个 tenant id。"""
    user = current_user()
    if not user:
        return None
    from models import _get_db
    db = _get_db()
    row = db.execute(
        "SELECT tenant_id FROM tenant_members WHERE user_id = ? LIMIT 1",
        (user["id"],),
    ).fetchone()
    return row["tenant_id"] if row else None


# ── 装饰器 ──────────────────────────────────────────


def login_required(view):
    """装饰器:未登录重定向到 /login?next=<原路径>。"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            next_url = request.path
            if request.query_string:
                next_url += "?" + request.query_string.decode("utf-8")
            return redirect(url_for("login", next=next_url))
        return view(*args, **kwargs)
    return wrapper
