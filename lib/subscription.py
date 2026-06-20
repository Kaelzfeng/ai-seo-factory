# -*- coding: utf-8 -*-
"""lib/subscription.py · SaaS 订阅逻辑

每个租户自动绑定套餐；生成前检查额度；超额 / 过期则拒绝并返回明确原因。
"""

import time
from models import (
    get_plan,
    get_active_subscription,
    create_subscription,
    get_monthly_usage,
)


# ── 常量 ────────────────────────────────────────────


class SubscriptionError(Exception):
    """订阅相关问题（超限、过期、无订阅）。"""
    def __init__(self, message: str, code: str = "subscription_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def ensure_default_plans():
    """套餐在 models._seed_plans 中随建表自动写入,此处仅为显式调用入口。"""
    # 首次 get_db() 就会触发 _seed_plans,这里只确保模块可被显式调用。
    from models import _get_db
    _get_db()  # 触发建表 + seed


def create_free_subscription(tenant_id: int) -> int:
    """为新 tenant 创建 Free 订阅。返回 subscription id。"""
    return create_subscription(tenant_id, plan_code="free", status="active")


def is_subscription_active(tenant_id: int) -> bool:
    """订阅是否存在且 status=active 且未过期。"""
    from models import is_subscription_active as _isa
    return _isa(tenant_id)


def check_generation_allowed(tenant_id: int) -> dict:
    """检查 tenant 是否可以生成新内容。

    返回:
        {"allowed": True}  或
        {"allowed": False, "reason": "...", "code": "..."}

    规则:
        1. 必须有 active subscription（无则为自动创建 Free）
        2. subscription 不能过期
        3. 本月 generation 数不能 >= monthly_generation_limit
        4. 本月 token 数不能 >= monthly_token_limit
    """
    # 先检查是否有任何订阅(含非 active)
    from models import _get_db
    db = _get_db()
    any_sub = db.execute(
        "SELECT * FROM subscriptions WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1",
        (tenant_id,),
    ).fetchone()
    has_any_subscription = any_sub is not None

    # 懒纠正：完全没有订阅才自动建 Free
    sub = get_active_subscription(tenant_id)
    if sub is None:
        if has_any_subscription:
            # 有订阅但非 active(例如已取消) → 不自动创建,直接拒绝
            status = dict(any_sub).get("status", "unknown")
            return {"allowed": False,
                    "reason": f"订阅状态为 {status},无法生成。",
                    "code": "subscription_inactive"}
        # 真·无订阅 → 自动建 Free
        sub_id = create_free_subscription(tenant_id)
        sub = get_active_subscription(tenant_id)
        if sub is None:
            return {"allowed": False,
                    "reason": "无法创建默认订阅,请联系管理员。",
                    "code": "no_subscription"}

    # 过期检查
    expire_at = sub.get("expire_at")
    if expire_at:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        if expire_at < now:
            return {"allowed": False,
                    "reason": f"订阅已于 {expire_at} 过期,请续费。",
                    "code": "subscription_expired"}

    # 状态检查
    if sub.get("status") != "active":
        return {"allowed": False,
                "reason": f"订阅状态为 {sub.get('status')},无法生成。",
                "code": "subscription_inactive"}

    # 额度检查
    monthly = get_monthly_usage(tenant_id)
    gen_used = 0
    token_used = 0
    for row in monthly:
        if row["kind"] == "generation":
            gen_used = row["total"]
        elif row["kind"] == "token":
            token_used = row["total"]

    gen_limit = sub.get("monthly_generation_limit", 3)
    token_limit = sub.get("monthly_token_limit", 100000)

    if gen_used >= gen_limit:
        return {"allowed": False,
                "reason": f"本月已生成 {gen_used}/{gen_limit} 篇,已达 Free 额度上限。",
                "code": "generation_limit_reached",
                "usage": {"generations_used": gen_used, "generations_limit": gen_limit}}

    if token_used >= token_limit:
        return {"allowed": False,
                "reason": f"本月已消耗 {token_used}/{token_limit} token,已达额度上限。",
                "code": "token_limit_reached",
                "usage": {"tokens_used": token_used, "tokens_limit": token_limit}}

    return {"allowed": True,
            "subscription": {
                "plan_code": sub.get("plan_code", "free"),
                "plan_name": sub.get("plan_name", "Free"),
                "generations_used": gen_used,
                "generations_limit": gen_limit,
                "tokens_used": token_used,
                "tokens_limit": token_limit,
            }}


def get_subscription_status(tenant_id: int) -> dict:
    """获取当前订阅的完整状态(供 API 返回)。"""
    sub = get_active_subscription(tenant_id)
    if sub is None:
        return {"subscription": None, "plan": None, "usage": {}}

    usage = {}
    monthly = get_monthly_usage(tenant_id)
    for row in monthly:
        usage[row["kind"]] = row["total"]

    return {
        "subscription": {
            "id": sub["id"],
            "plan_code": sub["plan_code"],
            "status": sub["status"],
            "started_at": sub["started_at"],
            "expire_at": sub.get("expire_at"),
        },
        "plan": {
            "name": sub.get("plan_name", ""),
            "monthly_generation_limit": sub.get("monthly_generation_limit", 0),
            "monthly_token_limit": sub.get("monthly_token_limit", 0),
            "max_projects": sub.get("max_projects", 0),
            "max_sites": sub.get("max_sites", 0),
            "price_cents": sub.get("price_cents", 0),
        },
        "usage": usage,
    }
