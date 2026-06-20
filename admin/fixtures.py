# -*- coding: utf-8 -*-
"""admin/fixtures.py · 超级管理员演示数据

所有 fixture 数据供 admin 模板渲染,纯 Python dict,零网络依赖。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Tenant ──────────────────────────────────────────

TENANTS = [
    {
        "id": 1,
        "name": "Northwind Retail",
        "plan": "Free",
        "status": "Active",
    },
    {
        "id": 2,
        "name": "萌翻天食品",
        "plan": "Free",
        "status": "Active",
    },
]

# ── Projects ────────────────────────────────────────

PROJECTS = [
    {
        "id": 1,
        "tenant_id": 1,
        "name": "PU Leather Export",
        "locale": "en-US",
        "domain": "demo-leather.example.com",
        "cms": "WordPress",
    },
    {
        "id": 2,
        "tenant_id": 2,
        "name": "萌食出海",
        "locale": "zh-CN",
        "domain": "mengfan.example.com",
        "cms": "WordPress",
    },
]

# ── Members ─────────────────────────────────────────

MEMBERS = [
    {
        "id": 1,
        "tenant_id": 1,
        "name": "Kai Lin",
        "role": "超级管理员",
        "scope": "跨租户全部数据",
    },
    {
        "id": 2,
        "tenant_id": 2,
        "name": "李小萌",
        "role": "Owner",
        "scope": "萌翻天食品",
    },
]

# ── Feasibility ─────────────────────────────────────

FEASIBILITY = {
    "score": 82,
    "verdict": "Go",
    "factors": [
        {
            "name": "搜索需求",
            "score": 90,
            "weight": 25,
            "evidence": "月搜索量 8.2K,3 年稳定增长。",
            "confidence": "High",
            "status": "pass",
        },
        {
            "name": "竞品强度",
            "score": 75,
            "weight": 20,
            "evidence": "首页 4/10 为内容型站点,非电商霸屏。",
            "confidence": "Medium",
            "status": "pass",
        },
        {
            "name": "内容差距",
            "score": 85,
            "weight": 20,
            "evidence": "Top 3 文章均缺少规格表与认证清单。",
            "confidence": "High",
            "status": "pass",
        },
        {
            "name": "商业意图匹配",
            "score": 80,
            "weight": 15,
            "evidence": "B2B 询盘意图比例 38%,高于行业均值 22%。",
            "confidence": "Medium",
            "status": "pass",
        },
        {
            "name": "E-E-A-T 可覆盖",
            "score": 78,
            "weight": 10,
            "evidence": "可引用 ISO/ASTM 标准,但暂无作者署名。",
            "confidence": "Low",
            "status": "warn",
        },
        {
            "name": "技术实现难度",
            "score": 88,
            "weight": 10,
            "evidence": "8 页内容结构可复用,pillar + cluster 架构一次搭建可支撑 40+ 长尾。",
            "confidence": "High",
            "status": "pass",
        },
    ],
}

# ── Modules (11 个) ─────────────────────────────────

MODULES = [
    {"key": "platform", "letter": "P", "label": "平台管理", "sub": "租户/项目/用户与账单",
     "icon": "dashboard", "children": []},
    {"key": "seo", "letter": "S", "label": "SEO 策略", "sub": "可行性·竞品·关键词·透明",
     "icon": "travel_explore", "children": [
         {"key": "feasibility", "label": "可行性报告"},
         {"key": "competitors", "label": "竞品拆解"},
         {"key": "keyword_map", "label": "关键词地图"},
     ]},
    {"key": "projects", "letter": "J", "label": "项目管理", "sub": "项目/站点/CMS 配置",
     "icon": "folder_managed", "children": []},
    {"key": "cms", "letter": "C", "label": "CMS 工作台", "sub": "内容日历·草稿·审核",
     "icon": "edit_note", "children": []},
    {"key": "content", "letter": "W", "label": "内容生成", "sub": "AI 写作·质检·润色",
     "icon": "draw", "children": []},
    {"key": "publish", "letter": "U", "label": "发布管理", "sub": "WordPress·调度·回链",
     "icon": "rocket_launch", "children": []},
    {"key": "monitor", "letter": "M", "label": "监控面板", "sub": "排名·流量·健康",
     "icon": "monitoring", "children": []},
    {"key": "data", "letter": "D", "label": "数据中心", "sub": "用量·token·审计",
     "icon": "bar_chart_4_bars", "children": []},
    {"key": "rbac", "letter": "R", "label": "权限与安全", "sub": "角色·成员·API 密钥",
     "icon": "admin_panel_settings", "children": []},
    {"key": "settings", "letter": "G", "label": "系统设置", "sub": "全局配置·日志·集成",
     "icon": "settings", "children": []},
    {"key": "agent", "letter": "A", "label": "Agent & Skill", "sub": "Skill 注册·编排·市场",
     "icon": "robot_2", "children": []},
]

# ── Skills ──────────────────────────────────────────

SKILLS = [
    {"name": "keyword-cluster", "status": "active", "version": "1.0"},
    {"name": "seo-content", "status": "active", "version": "1.1"},
    {"name": "quality-rubric", "status": "active", "version": "1.0"},
    {"name": "seo-content-polish", "status": "active", "version": "1.0"},
    {"name": "design-system", "status": "active", "version": "1.0"},
    {"name": "wp-publish", "status": "active", "version": "1.0"},
]

SKILL_ROADMAP = [
    {"name": "competitor-monitor", "phase": "Phase 2", "description": "竞品排名监控"},
    {"name": "internal-linking", "phase": "Phase 2", "description": "内链自动优化"},
    {"name": "multi-lang", "phase": "Phase 3", "description": "多语言生成"},
    {"name": "image-gen", "phase": "Phase 3", "description": "AI 配图"},
    {"name": "a-b-testing", "phase": "Phase 4", "description": "标题 A/B 测试"},
]

# ── Plans & Subscriptions ───────────────────────────

PLANS = [
    {"code": "free", "name": "Free", "monthly_generation_limit": 3,
     "monthly_token_limit": 100000, "max_projects": 1, "max_sites": 1,
     "competitor_analysis_limit": 1, "price_cents": 0},
]

SUBSCRIPTIONS = [
    {"tenant_id": 1, "plan_code": "free", "status": "active"},
    {"tenant_id": 2, "plan_code": "free", "status": "active"},
]

USAGE_SUMMARY = {
    "generations": 2,
    "tokens": 45000,
    "total_logs": 5,
}

# ── Keywords (演示用) ───────────────────────────────

KEYWORDS = [
    {"text": "PU leather", "intent": "commercial", "source": "seed",
     "support": 9, "keyword": "PU leather", "priority": 10},
    {"text": "PU leather vs genuine leather", "intent": "comparison",
     "source": "google", "support": 5, "keyword": "PU leather vs genuine leather",
     "priority": 8},
    {"text": "PU leather for furniture", "intent": "commercial",
     "source": "google", "support": 4, "keyword": "PU leather for furniture",
     "priority": 7},
    {"text": "is PU leather durable", "intent": "informational",
     "source": "google", "support": 3, "keyword": "is PU leather durable",
     "priority": 6, "is_question": True},
    {"text": "microfiber PU leather wholesale", "intent": "commercial",
     "source": "google", "support": 3, "keyword": "microfiber PU leather wholesale",
     "priority": 5},
]


# ── Keyword Map 演示数据 ────────────────────────────

KW_CLUSTERS = [
    {
        "name": "PU Leather Sourcing",
        "intent": "commercial",
        "pages": 3,
        "keywords": ["PU leather", "PU leather supplier", "PU leather wholesale"],
        "label": "采购决策",
        "icon": "shopping_cart",
    },
    {
        "name": "PU Leather vs Genuine",
        "intent": "comparison",
        "pages": 2,
        "keywords": ["PU leather vs genuine leather", "PU leather vs real leather", "synthetic vs genuine leather"],
        "label": "对比分析",
        "icon": "compare_arrows",
    },
    {
        "name": "Is PU Leather Durable",
        "intent": "informational",
        "pages": 2,
        "keywords": ["is PU leather durable", "is PU leather waterproof", "PU leather durability", "PU leather lifespan"],
        "label": "信息查询",
        "icon": "help_outline",
    },
    {
        "name": "PU Leather for Furniture",
        "intent": "commercial",
        "pages": 2,
        "keywords": ["PU leather for furniture", "PU leather sofa", "PU leather upholstery"],
        "label": "应用场景",
        "icon": "chair",
    },
    {
        "name": "Microfiber PU",
        "intent": "commercial",
        "pages": 1,
        "keywords": ["microfiber PU leather", "microfiber PU leather wholesale", "microfiber PU bags"],
        "label": "细分品类",
        "icon": "category",
    },
    {
        "name": "PU Leather Care",
        "intent": "informational",
        "pages": 1,
        "keywords": ["how to clean PU leather", "PU leather care", "PU leather maintenance"],
        "label": "使用养护",
        "icon": "clean_hands",
    },
]

KW_PILLAR = {"name": "PU leather", "keyword": "PU leather"}

# ── Transparency 演示数据 ───────────────────────────

TRANSPARENCY_PAGE = {
    "title": "PU Leather for Automotive Seats and Interiors",
    "page": "pu-leather-for-automotive",
    "score": 78,
    "passed": True,
    "breakdown": [
        {"dim": "keyword_usage", "score": 12, "max": 15, "note": "目标词 automotive 未进标题,但在 H2 与正文出现 4 次"},
        {"dim": "structure", "score": 13, "max": 15, "note": "h2→h3 层级正确,无跳级"},
        {"dim": "depth_wordcount", "score": 14, "max": 15, "note": "正文 1120 词,段落长度适中"},
        {"dim": "internal_links", "score": 12, "max": 15, "note": "4 条站内链接,覆盖 pillar 与相关对比页"},
        {"dim": "content_uniqueness", "score": 14, "max": 15, "note": "规格表独有,非复用模板片段"},
        {"dim": "meta_title_quality", "score": 13, "max": 15, "note": "标题 62 字符,含关键词但略长"},
    ],
    "placements": [
        {"kw": "PU leather for car seats", "where": "标题", "hit": False},
        {"kw": "automotive PU leather", "where": "H2 + 正文 4 处", "hit": True},
        {"kw": "FMVSS 302", "where": "规格表", "hit": True},
        {"kw": "low-fogging", "where": "H3 + 正文 2 处", "hit": True},
        {"kw": "Martindale automotive", "where": "正文 1 处", "hit": True},
        {"kw": "水解老化 automotive", "where": "未进标题", "hit": False},
    ],
}

# ── Agent Skill 演示数据 ─────────────────────────────

AGENT_SKILLS = [
    {
        "name": "keyword-cluster",
        "label": "关键词聚类",
        "icon": "hub",
        "role": "Planner",
        "status": "已上线",
        "note": "从种子关键词抓取搜索建议,按意图聚类为 pillar-cluster 结构,产出 7-15 页配额分配。",
    },
    {
        "name": "seo-content",
        "label": "SEO 内容生成",
        "icon": "edit_note",
        "role": "Writer",
        "status": "已上线",
        "note": "按页型(pillar/comparison/guide/FAQ/product)生成符合 E-E-A-T 的工业品内容,逐页产出 title/meta/html/image_query。",
    },
    {
        "name": "quality-rubric",
        "label": "质量评分",
        "icon": "fact_check",
        "role": "Polisher",
        "status": "已上线",
        "note": "确定性质检:六维度合计 100 分,反 AI slop 黑名单,规格信号奖励。≥70 分通过。",
    },
    {
        "name": "seo-content-polish",
        "label": "SEO 润色",
        "icon": "auto_fix_high",
        "role": "Polisher",
        "status": "已上线",
        "note": "根据质量扣分理由精准修正页面,复评后择优保留。无 issue 不调 LLM。",
    },
    {
        "name": "design-system",
        "label": "设计系统",
        "icon": "palette",
        "role": "Renderer",
        "status": "已上线",
        "note": "三套主题(editorial/atelier/blueprint)驱动 HTML 渲染:站内链接重写、JSON-LD 注入、质检横幅。",
    },
    {
        "name": "wp-publish",
        "label": "WordPress 发布",
        "icon": "rocket_launch",
        "role": "Publisher",
        "status": "已上线",
        "note": "REST API 发文 + SEO meta 写入 + 分类/标签 get-or-create。dry-run 零网络。",
    },
]

AGENT_ROADMAP = [
    {
        "phase": "Phase 1",
        "title": "内容工厂核心闭环",
        "detail": "关键词 → 生成 → 质检 → 润色 → 渲染 → 发布,6 组件全链路跑通。",
        "eta": "已完成",
        "status": "已完成",
    },
    {
        "phase": "Phase 2",
        "title": "SaaS 订阅骨架",
        "detail": "多租户、套餐额度、用量统计、超额阻断。注册即开 Free 租户。",
        "eta": "进行中",
        "status": "进行中",
    },
    {
        "phase": "Phase 3",
        "title": "意图反问 Agent",
        "detail": "多轮对话式 intake:自然语言输入 → 结构化 brief → 自动配参生成。",
        "eta": "4-6 周",
        "status": "待启动",
    },
    {
        "phase": "Phase 4",
        "title": "竞品监控与排名追踪",
        "detail": "竞品页面变更检测、关键词排名日报、内容差距自动分析。",
        "eta": "8-12 周",
        "status": "待启动",
    },
    {
        "phase": "Phase 5",
        "title": "多语言 + A/B 测试",
        "detail": "一键多语种翻译生成、标题/描述 A/B 实验、转化率归因面板。",
        "eta": "12-16 周",
        "status": "待启动",
    },
]


# ── Helper ──────────────────────────────────────────


def load_competitors() -> list[dict]:
    """读取 research/competitor-dossiers.json 返回竞品列表。

    如果文件不存在或解析失败,返回空列表,不报错。
    """
    path = ROOT / "research" / "competitor-dossiers.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("competitors", [])
    except (json.JSONDecodeError, OSError):
        return []


def context(active: str, tenant_index: int = 0) -> dict:
    """为 admin 模板构建最小上下文。

    Args:
        active: 当前激活的模块 key(如 "feasibility")
        tenant_index: 用第几个 tenant(0=Northwind, 1=萌翻天)

    Returns:
        {active, tenant, project, member, modules, tenants, projects, members,
         feasibility, competitors, keywords, skills, skill_roadmap}
    """
    idx = min(tenant_index, len(TENANTS) - 1)
    return {
        "active": active,
        "tenant": TENANTS[idx],
        "project": PROJECTS[idx] if idx < len(PROJECTS) else None,
        "member": MEMBERS[idx] if idx < len(MEMBERS) else None,
        "modules": MODULES,
        "tenants": TENANTS,
        "projects": PROJECTS,
        "members": MEMBERS,
        "feasibility": FEASIBILITY,
        "competitors": load_competitors(),
        "keywords": KEYWORDS,
        "skills": SKILLS,
        "skill_roadmap": SKILL_ROADMAP,
        "plans": PLANS,
        "subscriptions": SUBSCRIPTIONS,
        "usage_summary": USAGE_SUMMARY,
    }
