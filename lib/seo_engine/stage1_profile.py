# -*- coding: utf-8 -*-
"""lib/seo_engine/stage1_profile.py · Stage 1: 生意画像

根据 clarified scope 生成 BusinessProfile。
先用规则 + 现有 industry YAML,再 LLM 补充。
LLM 失败不能阻断。
"""

import time
from pathlib import Path

from lib.seo_engine.schemas import BusinessProfile


ROOT = Path(__file__).resolve().parent.parent.parent


# ── 基础构建 ──────────────────────────────────────────


def build_business_profile(scope: dict, project: dict = None) -> BusinessProfile:
    """根据 scope 构建 BusinessProfile。

    Args:
        scope: clarified scope dict from stage0
        project: 可选的项目 dict(用于读取 industry YAML)

    Returns:
        BusinessProfile instance
    """
    industry = (scope or {}).get("industry", "") or "General"
    language = (scope or {}).get("language", "English")
    target_market = (scope or {}).get("target_market", "")
    business_type = (scope or {}).get("business_type", "")

    # 默认值
    target_markets = [target_market] if target_market else ["global"]
    languages = [language] if language else ["English"]

    profile = BusinessProfile(
        industry=industry,
        business_type=business_type or "B2B",
        target_markets=target_markets,
        languages=languages,
        products=[industry],
        buyer_personas=[],
        value_propositions=[],
        constraints=[],
        tone="Professional, factual",
        terminology=[],
        source_input=json.dumps(scope, ensure_ascii=False) if scope else "",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    # 确定性 fallback: 根据行业补充 products / personas / terminology
    _deterministic_enrich(profile)

    # 从项目 industry YAML 补充 tone / terminology / products
    if project:
        _enrich_from_project(profile, project)

    # LLM 补充 buyer_personas / value_propositions / terminology
    _llm_enrich(profile)

    return profile


# ── 确定性行业知识库 ──────────────────────────────────


_INDUSTRY_DEFAULTS = {
    "pu leather": {
        "products": [
            "PU leather", "synthetic leather", "microfiber PU leather",
            "PU leather for furniture", "PU leather for automotive",
            "PU leather for bags and accessories",
        ],
        "buyer_personas": [
            "Furniture manufacturer sourcing durable upholstery materials",
            "Automotive interior buyer seeking OEM-grade synthetic leather",
            "Bag and accessories brand looking for customizable textures",
            "Wholesale distributor of synthetic leather materials",
        ],
        "value_propositions": [
            "Customizable textures, colors, and finishes",
            "Stable bulk supply with consistent quality",
            "Application-specific material guidance and technical support",
            "Export-ready B2B support with international logistics",
        ],
        "terminology": [
            "PU leather", "synthetic leather", "microfiber leather",
            "PVC leather", "genuine leather", "abrasion resistance",
            "hydrolysis resistance", "backing fabric", "embossing",
            "GSM (grams per square meter)", "thickness gauge",
            "color fastness", "UV resistance", "peel strength",
        ],
        "business_type": "B2B supplier",
        "tone": "Professional, factual, confident manufacturer voice. No fluff. Lead with specifications and real-world performance data.",
    },
    "solar panel": {
        "products": [
            "Solar panels", "monocrystalline panels", "polycrystalline panels",
            "bifacial solar panels", "solar panel mounting systems",
        ],
        "buyer_personas": [
            "Solar installer and EPC contractor",
            "Wholesale distributor of renewable energy equipment",
            "Commercial project developer",
        ],
        "value_propositions": [
            "Tier-1 quality with IEC certification",
            "Competitive pricing for bulk orders",
            "Technical support and system design assistance",
        ],
        "terminology": [
            "Watt peak (Wp)", "conversion efficiency", "IEC 61215",
            "monocrystalline", "polycrystalline", "bifacial",
            "temperature coefficient", "degradation rate",
        ],
        "business_type": "B2B supplier",
        "tone": "Technical, data-driven, professional",
    },
}


def _deterministic_enrich(profile: BusinessProfile):
    """根据行业名匹配确定性知识库,补充 products/personas/terminology。"""
    industry_lower = profile.industry.lower().strip()

    # 尝试精确匹配或子串匹配
    best_match = None
    for key, defaults in _INDUSTRY_DEFAULTS.items():
        if key in industry_lower or industry_lower in key:
            best_match = defaults
            break

    if not best_match:
        # 通用回退: 从 industry 名生成基本内容
        ind = profile.industry.strip()
        if not profile.products or len(profile.products) <= 1:
            profile.products = [ind, f"{ind} for industrial use", f"{ind} variants"]
        if not profile.buyer_personas:
            profile.buyer_personas = [
                f"Industrial buyer sourcing {ind}",
                f"Wholesale distributor of {ind}",
            ]
        if not profile.value_propositions:
            profile.value_propositions = [
                f"High-quality {ind} products",
                "Competitive pricing for bulk orders",
                "Export-ready logistics support",
            ]
        if not profile.terminology:
            profile.terminology = [ind, f"{ind} specification", "industry standards"]
        if not profile.business_type or profile.business_type == "B2B":
            profile.business_type = "B2B supplier"
        return

    # 应用确定性知识库
    if not profile.products or len(profile.products) <= 1:
        profile.products = list(best_match.get("products", profile.products))
    if not profile.buyer_personas:
        profile.buyer_personas = list(best_match.get("buyer_personas", []))
    if not profile.value_propositions:
        profile.value_propositions = list(best_match.get("value_propositions", []))
    if not profile.terminology:
        profile.terminology = list(best_match.get("terminology", []))
    if best_match.get("business_type") and (not profile.business_type or profile.business_type == "B2B"):
        profile.business_type = best_match["business_type"]
    if best_match.get("tone") and profile.tone == "Professional, factual":
        profile.tone = best_match["tone"]


def _enrich_from_project(profile: BusinessProfile, project: dict):
    """从项目的 industry YAML 中读取补充信息。"""
    import json
    try:
        config_path = project.get("industry_config", "")
        if not config_path:
            return
        if not Path(config_path).exists():
            return

        import yaml
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

        if cfg.get("tone"):
            profile.tone = cfg["tone"]
        if cfg.get("terminology"):
            terms = cfg["terminology"]
            if isinstance(terms, str):
                profile.terminology = [t.strip() for t in terms.split(",") if t.strip()]
            elif isinstance(terms, list):
                profile.terminology = terms
        if cfg.get("products") and isinstance(cfg.get("products"), list):
            profile.products = cfg["products"]
        if cfg.get("audience"):
            profile.buyer_personas.append(cfg["audience"])
        if cfg.get("market"):
            profile.target_markets = [m.strip() for m in cfg["market"].split(",")]
        if cfg.get("language"):
            profile.languages = [cfg["language"]]
    except Exception:
        pass


def _llm_enrich(profile: BusinessProfile):
    """用 LLM 补充 buyer_personas / value_propositions / terminology。
    失败不阻断,保留已有值。
    """
    try:
        from lib.llm import default_model, structured

        schema = {
            "type": "object",
            "properties": {
                "buyer_personas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 buyer persona descriptions",
                },
                "value_propositions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 unique value propositions",
                },
                "terminology": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5-10 industry-specific technical terms",
                },
            },
            "required": ["buyer_personas", "value_propositions"],
        }

        result = structured(
            model=default_model("planner"),
            system="You are a B2B industry analyst. Return valid JSON only.",
            user=f"""Analyze this business:

Industry: {profile.industry}
Business type: {profile.business_type}
Target markets: {', '.join(profile.target_markets)}
Products: {', '.join(profile.products)}
Tone: {profile.tone}

Return:
- 2-3 buyer personas (who buys and why)
- 2-3 unique value propositions
- 5-10 industry-specific terminology/standards/units""",
            schema=schema,
            max_tokens=1024,
        )

        if result and isinstance(result, dict):
            if result.get("buyer_personas"):
                personas = [p for p in result["buyer_personas"] if p.strip()]
                if personas:
                    profile.buyer_personas = personas
            if result.get("value_propositions"):
                props = [p for p in result["value_propositions"] if p.strip()]
                if props:
                    profile.value_propositions = props
            if result.get("terminology"):
                terms = [t for t in result["terminology"] if t.strip()]
                if terms:
                    # 合并而非覆盖
                    existing = set(t.lower() for t in profile.terminology)
                    for t in terms:
                        if t.lower() not in existing:
                            profile.terminology.append(t)
                            existing.add(t.lower())
    except Exception:
        pass


# ── 验证 ──────────────────────────────────────────────


def validate_business_profile(profile: BusinessProfile) -> dict:
    """验证 BusinessProfile 是否满足最低要求。

    Returns:
        {"valid": bool, "issues": [...]}
    """
    issues = []

    if not profile.industry or not profile.industry.strip():
        issues.append("industry 不能为空")
    if not profile.target_markets:
        issues.append("target_markets 至少需要 1 个")
    if not profile.languages:
        issues.append("languages 至少需要 1 个")
    if not profile.products:
        issues.append("products 至少需要 1 个")
    if not profile.buyer_personas:
        issues.append("buyer_personas 至少需要 1 个(可使用默认值)")
    if not profile.tone:
        issues.append("tone 应有默认值")
    if not isinstance(profile.terminology, list):
        issues.append("terminology 必须是 list")

    # 自动修复可修复的
    if not profile.tone:
        profile.tone = "Professional, factual"

    return {"valid": len(issues) == 0, "issues": issues}


# ── Prompt 上下文 ──────────────────────────────────────


def profile_to_prompt_context(profile: BusinessProfile) -> str:
    """将 BusinessProfile 输出为供后续 Stage 使用的 prompt 上下文字符串。"""
    lines = [
        f"INDUSTRY: {profile.industry}",
        f"BUSINESS TYPE: {profile.business_type}",
        f"TARGET MARKETS: {', '.join(profile.target_markets)}",
        f"LANGUAGES: {', '.join(profile.languages)}",
        f"PRODUCTS: {', '.join(profile.products)}",
        f"TONE: {profile.tone}",
    ]
    if profile.buyer_personas:
        lines.append("BUYER PERSONAS:")
        for p in profile.buyer_personas:
            lines.append(f"  - {p}")
    if profile.value_propositions:
        lines.append("VALUE PROPOSITIONS:")
        for v in profile.value_propositions:
            lines.append(f"  - {v}")
    if profile.terminology:
        lines.append(f"TERMINOLOGY: {', '.join(profile.terminology)}")
    if profile.constraints:
        lines.append("CONSTRAINTS:")
        for c in profile.constraints:
            lines.append(f"  - {c}")

    return "\n".join(lines)


import json  # noqa: E402 (used in build_business_profile)
