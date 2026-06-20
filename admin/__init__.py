# -*- coding: utf-8 -*-
"""admin · 超级管理员 Blueprint

只渲染已有 templates/admin/ 模板,不新建模板。
"""

import json
from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from admin.fixtures import (
    TENANTS, PROJECTS, MEMBERS, FEASIBILITY, MODULES,
    SKILLS, SKILL_ROADMAP, KEYWORDS, PLANS, SUBSCRIPTIONS, USAGE_SUMMARY,
    KW_CLUSTERS, KW_PILLAR, TRANSPARENCY_PAGE,
    AGENT_SKILLS, AGENT_ROADMAP,
    load_competitors, context as fx_context,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── 上下文构建 ──────────────────────────────────────


def _build_context(active: str) -> dict:
    """根据 query param ?tenant= 选择租户上下文。"""
    tenant_key = request.args.get("tenant", "").strip().lower()
    tenant_index = 0
    if tenant_key == "herz":
        tenant_index = 1
    elif tenant_key.isdigit():
        tenant_index = int(tenant_key) % len(TENANTS)

    ctx = fx_context(active, tenant_index=tenant_index)

    # 添加 Flask url_for 到上下文(模板使用)
    ctx["url_for"] = url_for
    return ctx


# ── 路由 ────────────────────────────────────────────


@admin_bp.route("/")
def index():
    """超级管理员首页 —— 默认显示可行性报告。"""
    ctx = _build_context("feasibility")
    ctx["feasibility"] = FEASIBILITY
    return render_template("admin/feasibility.html", **ctx)


@admin_bp.route("/feasibility")
def feasibility():
    """SEO 可行性评分报告。"""
    ctx = _build_context("feasibility")
    ctx["feasibility"] = FEASIBILITY
    return render_template("admin/feasibility.html", **ctx)


@admin_bp.route("/competitors")
def competitors():
    """竞品拆解页。"""
    ctx = _build_context("competitors")
    ctx["competitors"] = load_competitors()
    return render_template("admin/competitors.html", **ctx)


@admin_bp.route("/keywords")
def keyword_map():
    """关键词地图页。"""
    ctx = _build_context("keyword_map")
    ctx["keywords"] = KEYWORDS
    ctx["kw"] = {"clusters": KW_CLUSTERS}
    ctx["pillar"] = KW_PILLAR
    return render_template("admin/keyword_map.html", **ctx)


@admin_bp.route("/transparency")
def transparency():
    """生成档案透明页。"""
    ctx = _build_context("transparency")
    ctx["t"] = TRANSPARENCY_PAGE
    return render_template("admin/transparency.html", **ctx)


@admin_bp.route("/agent")
def agent_skill():
    """Agent & Skill 管理页。"""
    ctx = _build_context("agent")
    ctx["skills"] = AGENT_SKILLS
    ctx["roadmap"] = AGENT_ROADMAP
    ctx["skill_roadmap"] = SKILL_ROADMAP
    return render_template("admin/agent_skill.html", **ctx)


@admin_bp.route("/m/<key>")
def module(key):
    """通用存根模块页(平台管理/项目管理/... 等 demo 占位)。"""
    ctx = _build_context(key)
    # 找到对应模块
    m = None
    for mod in MODULES:
        if mod["key"] == key:
            m = mod
            break
        if mod.get("children"):
            for child in mod["children"]:
                if child["key"] == key:
                    m = child
                    break
    if m is None:
        m = {"key": key, "label": key, "sub": "模块", "icon": "dashboard"}

    ctx["m"] = m
    return render_template("admin/_stub.html", **ctx)


# ── JSON API ────────────────────────────────────────


@admin_bp.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "service": "ai-seo-content-factory"})


@admin_bp.route("/api/subscription-summary")
def api_subscription_summary():
    """返回所有订阅摘要。"""
    return jsonify({
        "subscriptions": SUBSCRIPTIONS,
        "plans": PLANS,
    })


@admin_bp.route("/api/usage-summary")
def api_usage_summary():
    """返回演示用量摘要。"""
    return jsonify(USAGE_SUMMARY)
