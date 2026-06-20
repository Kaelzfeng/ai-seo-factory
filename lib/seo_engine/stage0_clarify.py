# -*- coding: utf-8 -*-
"""lib/seo_engine/stage0_clarify.py · Stage 0: 需求澄清

把自然语言输入收敛为可执行 scope。
必填槽位: industry, language, target_market
LLM 优先 + 确定性正则 fallback。
"""

import json
import re


# ── 确定性规则 ────────────────────────────────────────


def _deterministic_extract(user_input: str) -> dict:
    """纯正则提取 scope,不依赖 LLM。"""
    text = user_input or ""
    scope = {
        "industry": "",
        "language": "English",
        "target_market": "",
        "business_type": "",
    }

    # 语言检测
    if re.search(r"\b(Chinese|中文|Mandarin|Cantonese)\b", text, re.IGNORECASE):
        scope["language"] = "Chinese"
    elif re.search(r"\b(Spanish|Español)\b", text, re.IGNORECASE):
        scope["language"] = "Spanish"
    elif re.search(r"\b(English)\b", text, re.IGNORECASE):
        scope["language"] = "English"

    # 业务类型
    if re.search(r"\b(B2B|wholesale|export|supplier|manufacturer|factory)\b", text, re.IGNORECASE):
        scope["business_type"] = "B2B"
    elif re.search(r"\b(B2C|retail|ecommerce|shop|store)\b", text, re.IGNORECASE):
        scope["business_type"] = "B2C"

    # 市场
    market_parts = []
    if re.search(r"\b(global|worldwide|international)\b", text, re.IGNORECASE):
        market_parts.append("global")
    if re.search(r"\b(B2B|wholesale|export)\b", text, re.IGNORECASE):
        market_parts.append("B2B")
    if re.search(r"\b(US|USA|America|United States)\b", text):
        market_parts.append("US")
    if re.search(r"\b(Europe|European|EU)\b", text):
        market_parts.append("Europe")
    if re.search(r"\b(Asia|Asian)\b", text):
        market_parts.append("Asia")
    if re.search(r"\b(buyer|importer|procurement)\b", text, re.IGNORECASE):
        market_parts.append("buyers")
    scope["target_market"] = " ".join(market_parts) if market_parts else ""

    # 行业提取: 尝试从文本中提取首字母大写的专有名词链
    industry_candidates = re.findall(
        r'\b((?:[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|and|of|for|&)\s*)*)+)\b', text
    )
    if industry_candidates:
        # 过滤太通用或太短的
        filtered = [c for c in industry_candidates if len(c) > 3 and c.lower() not in (
            "i want", "english", "b2b", "export", "global", "site", "website",
            "the", "this", "that", "with", "from", "high quality",
        )]
        if filtered:
            scope["industry"] = filtered[0].strip()

    # 如果没有找到大写词,尝试查找 "for X" 或 "about X" 结构
    if not scope["industry"]:
        m = re.search(r'(?:for|about|on)\s+([A-Za-z][A-Za-z\s-]{2,40}?)(?:\s+(?:site|website|blog|export|B2B|business|company))?$', text, re.IGNORECASE)
        if m:
            scope["industry"] = m.group(1).strip()

    return scope


# ── LLM 提取 ──────────────────────────────────────────


def _llm_extract(user_input: str) -> dict | None:
    """用 LLM 从用户输入提取 scope 结构。"""
    try:
        from lib.llm import default_model, structured
        schema = {
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "Industry name in English, e.g. PU leather"},
                "language": {"type": "string", "description": "Target language, default English"},
                "target_market": {"type": "string", "description": "Target market, e.g. global B2B export"},
                "business_type": {"type": "string", "description": "B2B or B2C"},
            },
            "required": ["industry", "language", "target_market"],
        }
        result = structured(
            model=default_model("planner"),
            system="Extract business scope from user input. Return valid JSON only.",
            user=f"""Extract these fields from the user input:

User input: {user_input}

Return JSON with: industry (English name), language (e.g. English), target_market (e.g. global B2B export), business_type (B2B or B2C).""",
            schema=schema,
            max_tokens=512,
        )
        if result and isinstance(result, dict) and result.get("industry"):
            return result
    except Exception:
        pass
    return None


# ── 公开函数 ──────────────────────────────────────────


def missing_required_slots(scope: dict) -> list[str]:
    """返回缺失的必填槽位。"""
    missing = []
    if not (scope or {}).get("industry", "").strip():
        missing.append("industry")
    if not (scope or {}).get("target_market", "").strip():
        missing.append("target_market")
    if not (scope or {}).get("language", "").strip():
        missing.append("language")
    return missing


def needs_clarification(scope: dict) -> bool:
    """检查 scope 是否还需要追问。"""
    return len(missing_required_slots(scope)) > 0


def clarify_request(user_input: str, optional_url: str = None,
                    max_rounds: int = 3) -> dict:
    """把自然语言输入收敛为可执行 scope。

    Args:
        user_input: 用户自然语言输入
        optional_url: 可选 URL
        max_rounds: 最多追问轮数(由调用方管理,此处仅返回是否需要追问)

    Returns:
        {"ok": bool, "needs_clarification": bool,
         "scope": {...}, "questions": [...], "missing": [...]}
    """
    scope = {}

    # 1. 先尝试 LLM
    llm_result = _llm_extract(user_input)
    if llm_result:
        scope = llm_result

    # 2. LLM 失败或结果不完整 → 确定性 fallback
    det_result = _deterministic_extract(user_input)
    for key in ("industry", "language", "target_market", "business_type"):
        if not scope.get(key) and det_result.get(key):
            scope[key] = det_result[key]

    # 3. 从 URL 提取线索(如果有)
    if optional_url:
        domain = re.sub(r'^https?://(www\.)?', '', optional_url).split('/')[0]
        if not scope.get("industry"):
            # 尝试从域名提取行业词
            parts = re.findall(r'[a-zA-Z]{3,}', domain.replace('.', ' '))
            if parts:
                scope["industry"] = " ".join(parts[:2]).title()

    # 补默认值
    if not scope.get("language"):
        scope["language"] = "English"

    # 4. 检查缺失
    missing = missing_required_slots(scope)
    questions = []

    if "industry" in missing:
        questions.append("What industry / product are you targeting? (e.g. PU leather, solar panels)")
    if "target_market" in missing:
        questions.append("What is your target market? (e.g. global B2B export, US retail)")
    if "language" in missing:
        questions.append("What language should the content be in?")

    needs = len(missing) > 0

    return {
        "ok": not needs,
        "needs_clarification": needs,
        "scope": scope,
        "questions": questions,
        "missing": missing,
    }
