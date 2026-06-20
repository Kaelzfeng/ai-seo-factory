# -*- coding: utf-8 -*-
"""lib/seo_engine/stage2_blueprint.py · Stage 2: 站点蓝图

从 BusinessProfile 生成 SiteBlueprint:
- 关键词扩展 → 意图分类 → 主题聚类 → 页型映射 → 页面分配 → 链接图
"""

import json
import re
import time
from collections import defaultdict
from pathlib import Path

import yaml

from lib.seo_engine.schemas import (
    Keyword, Topic, PagePlan, SiteBlueprint, BusinessProfile,
)

ROOT = Path(__file__).resolve().parent.parent.parent


# ── Intent Rules Loading ──────────────────────────────


_INTENT_RULES = None


def _load_intent_rules() -> dict:
    """加载 intent_rules.yaml;失败时使用内置 fallback。"""
    global _INTENT_RULES
    if _INTENT_RULES is not None:
        return _INTENT_RULES

    rules_path = Path(__file__).resolve().parent / "intent_rules.yaml"
    try:
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            _INTENT_RULES = data.get("intents", {})
            if _INTENT_RULES:
                return _INTENT_RULES
    except Exception:
        pass

    # 内置 fallback (内容与 YAML 一致)
    _INTENT_RULES = {
        "comparison": {"keyword_contains": ["vs", "versus", "compare", "comparison", "difference", "difference between", "better than", "or", "v."], "keyword_regex": [r"\bvs\.?\b", r"\bv\.\s"]},
        "faq": {"keyword_contains": ["how", "what", "why", "when", "where", "which", "who", "is", "are", "does", "do", "can", "will", "should", "waterproof", "durable", "toxic", "safe"]},
        "product": {"keyword_contains": ["wholesale", "supplier", "manufacturer", "factory", "price", "cost", "buy", "for sale", "bulk", "export", "specification"]},
        "category": {"keyword_contains": ["types of", "kinds of", "categories of", "classification", "grades of", "varieties of"]},
        "guide": {"keyword_contains": ["guide", "how to", "tutorial", "introduction", "overview", "explained", "complete", "ultimate"]},
        "commercial": {"keyword_contains": ["best", "top", "review", "reviews", "rated", "quality", "premium", "professional", "benefits", "advantages"]},
        "transactional": {"keyword_contains": ["buy", "purchase", "order", "quote", "quotation", "sample", "inquiry", "contact"]},
        "informational": {"keyword_contains": ["what is", "definition", "meaning", "properties", "characteristics", "uses of", "applications of", "process", "manufacturing", "production"]},
    }
    return _INTENT_RULES


# ── Keyword Expansion ──────────────────────────────────


def expand_seed_keywords(profile: BusinessProfile,
                         seed_keywords: list[str] = None,
                         limit: int = 210) -> list[Keyword]:
    """关键词扩展。优先复用 keyword_scout.grounded_plan。

    Args:
        profile: BusinessProfile
        seed_keywords: 可选的种子关键词列表
        limit: 最大关键词数

    Returns:
        list of Keyword objects
    """
    if not seed_keywords:
        # 从 profile 推导种子
        seed_keywords = [profile.industry]
        if profile.products:
            for p in profile.products[:2]:
                if p.lower() != profile.industry.lower():
                    seed_keywords.append(p)

    all_keywords = []
    seen = set()

    for seed in seed_keywords[:3]:
        try:
            from lib.keyword_scout import grounded_plan
            gp = grounded_plan(seed, max_pages=min(15, limit // len(seed_keywords)))
            pool = gp.get("pool", {})
            for kw_text, kw_data in pool.items():
                kw_norm = kw_text.strip().lower()
                if kw_norm in seen:
                    continue
                seen.add(kw_norm)

                intent = _classify_intent_enhanced(kw_text)
                all_keywords.append(Keyword(
                    keyword=kw_text.strip(),
                    intent=intent,
                    priority=kw_data.get("support", 0),
                    language=profile.languages[0] if profile.languages else "English",
                    market=profile.target_markets[0] if profile.target_markets else "",
                    volume_hint=kw_data.get("support", 0) * 50,
                    difficulty_hint=max(10, 70 - kw_data.get("support", 0) * 5),
                    source="keyword_scout",
                    cluster_id="",
                ))
        except Exception:
            # keyword_scout 不可用 → 确定性 fallback
            fallback = _deterministic_expand(seed, profile)
            for kw in fallback:
                kw_norm = kw.keyword.lower()
                if kw_norm not in seen:
                    seen.add(kw_norm)
                    all_keywords.append(kw)

    return all_keywords[:limit]


def _deterministic_expand(seed: str, profile: BusinessProfile) -> list[Keyword]:
    """确定性关键词扩展(Phase 3.2: B2B-focused)。"""
    lang = profile.languages[0] if profile.languages else "English"
    seed_lower = seed.lower().strip()

    # B2B 优先的关键词模板
    modifiers = [
        # comparison (2)
        ("vs genuine leather", "comparison", 9),
        ("vs pvc leather", "comparison", 9),
        # applications (3)
        ("for furniture", "informational", 8),
        ("for automotive", "informational", 8),
        ("for bags and accessories", "informational", 7),
        # supplier-commercial (2)
        ("supplier", "product", 9),
        ("wholesale price", "product", 8),
        # faq / durability (2)
        ("durable waterproof", "faq", 7),
        ("safe eco friendly", "faq", 6),
        # guide / basics (2)
        ("guide", "guide", 10),
        ("types of", "category", 6),
        # supporting (3)
        ("specification", "informational", 5),
        ("manufacturer", "product", 8),
        ("factory export", "product", 7),
        # comparison additional
        ("vs real leather", "comparison", 8),
        # applications additional
        ("for sofa upholstery", "informational", 6),
        ("for car interior", "informational", 6),
    ]

    keywords = []
    for mod, intent, priority in modifiers:
        kw = f"{seed_lower} {mod}"
        keywords.append(Keyword(
            keyword=kw, intent=_classify_intent_enhanced(kw),
            priority=priority, language=lang,
            source="deterministic_fallback",
        ))
    return keywords


# ── Intent Classification ─────────────────────────────


def classify_intent(keyword: str) -> str:
    """增强意图分类: intent_rules.yaml + keyword_scout fallback。"""
    return _classify_intent_enhanced(keyword)


def _classify_intent_enhanced(kw: str) -> str:
    """优先级: intent_rules.yaml → keyword_scout.classify_intent → informational。"""
    rules = _load_intent_rules()
    kw_lower = kw.strip().lower()

    for intent_name, rule in rules.items():
        if intent_name == "default_intent":
            continue
        # keyword_contains — 使用词边界匹配避免 "do" in "random"
        contains = rule.get("keyword_contains", [])
        for pattern in contains:
            pat = pattern.strip().lower()
            # Multi-word patterns use substring; single words use \b boundary
            if " " in pat:
                if pat in kw_lower:
                    return intent_name
            else:
                if re.search(r'\b' + re.escape(pat) + r'\b', kw_lower):
                    return intent_name
        # keyword_regex
        regexes = rule.get("keyword_regex", [])
        for pat in regexes:
            try:
                if re.search(pat, kw_lower):
                    return intent_name
            except re.error:
                pass

    # Fallback to keyword_scout's classifier
    try:
        from lib.keyword_scout import classify_intent as _ks_classify
        ks_intent = _ks_classify(kw)
        # Map keyword_scout intents to our intents
        mapping = {
            "comparison": "comparison",
            "commercial": "commercial",
            "application": "guide",
            "informational": "informational",
            "other": "informational",
        }
        return mapping.get(ks_intent, "informational")
    except Exception:
        pass

    return "informational"


# ── Semantic Cluster Rules ────────────────────────────


_CLUSTER_RULES = [
    # (cluster_name, page_type, match_keywords, priority_boost)
    ("comparison", "comparison", ["vs", "versus", "compare", "comparison", "difference", "better than", " v ", " v."], 10),
    ("applications", "application", ["furniture", "automotive", "car seat", "car interior", "sofa", "chair", "bag", "shoe", "footwear", "interior", "upholstery", "garment", "clothing", "apparel"], 8),
    ("supplier-commercial", "product", ["supplier", "manufacturer", "wholesale", "factory", "export", "bulk", "price", "catalogue", "catalog", "for sale", "buyer", "sourcing", "procurement", "sample", "b2b"], 7),
    ("durability-safety", "faq", ["durable", "waterproof", "toxic", "safety", "safe", "eco friendly", "environmentally", "fire resistant", "abrasion", "hydrolysis", "uv resistant"], 8),
    ("consumer-care", "faq", ["care", "clean", "maintenance", "cleaning", "repair", "smell", "peeling", "cracking", "fading", "stain", "remove", "washing", "wash"], 3),
    ("faq-questions", "faq", ["what is", "how to", "how do", "why is", "why do", "can you", "should i", "does pu", "will pu", "is it"], 6),
    ("guide-basics", "guide", ["guide", "complete", "ultimate", "overview", "introduction", "explained", "definition", "properties", "characteristics", "beginners", "basics"], 10),
    ("product-category", "category", ["types of", "kinds of", "categories", "grades", "varieties", "microfiber", "pvc leather", "synthetic", "recycled"], 6),
]


# ── B2B Priority Scoring ──────────────────────────────


# 高优先级 B2B 关键词 → +boost
_B2B_HIGH_PRIORITY = {
    "supplier", "manufacturer", "wholesale", "bulk", "export", "b2b",
    "furniture", "automotive", "car interior", "bags", "upholstery",
    "applications", "types", "guide", "vs", "pvc", "genuine leather",
    "microfiber", "specification", "catalogue", "factory",
}

# 低优先级 consumer care 关键词 → -boost (不删除,只降级)
_CONSUMER_CARE = {
    "clean", "care", "repair", "smell", "peeling", "vegan",
    "safe", "toxic", "waterproof", "cracking", "fading", "stain",
    "remove", "washing",
}

# 事实风险关键词 → 需要改写
_FACT_RISK_PATTERNS = [
    (r"\bpu leather is real leather\b", "pu leather vs genuine leather", "comparison",
     "PU Leather vs Genuine Leather: Key Differences for B2B Buyers"),
    (r"\bis pu leather real leather\b", "pu leather vs genuine leather", "comparison",
     "PU Leather vs Genuine Leather: Key Differences for B2B Buyers"),
    (r"\bpu leather genuine leather\b", "pu leather vs genuine leather", "comparison",
     "PU Leather vs Genuine Leather: Key Differences for B2B Buyers"),
    (r"\bpu leather is genuine leather\b", "pu leather vs genuine leather", "comparison",
     "PU Leather vs Genuine Leather: Key Differences for B2B Buyers"),
    (r"\bis pu leather real\b", "is pu leather real leather", "faq",
     "Is PU Leather Real Leather? Material Facts for B2B Buyers"),
    (r"\bpu leather real\b", "pu leather vs genuine leather", "comparison",
     "PU Leather vs Genuine Leather: What B2B Buyers Need to Know"),
]


def _score_page_candidate(keyword: str, intent: str, cluster: str,
                          profile=None) -> int:
    """B2B 页面候选评分 (越高越优先)。

    - B2B 高优先级词: +3
    - Consumer care 词: -2
    - 事实风险: -10 (需要改写或排除)
    - cluster priority_boost 在分配时叠加
    """
    kw_lower = keyword.lower()
    score = 0

    for word in _B2B_HIGH_PRIORITY:
        if word in kw_lower:
            score += 3

    for word in _CONSUMER_CARE:
        if word in kw_lower:
            score -= 2

    if _has_fact_risk(keyword):
        score -= 10

    return score


def _is_b2b_relevant(keyword: str, profile=None) -> bool:
    """检查关键词是否与 B2B 相关。"""
    kw_lower = keyword.lower()
    b2b_signals = {"supplier", "manufacturer", "wholesale", "bulk", "export",
                   "b2b", "factory", "catalogue", "specification", "sourcing",
                   "procurement", "industrial", "commercial", "oem"}
    for sig in b2b_signals:
        if sig in kw_lower:
            return True
    return False


def _is_consumer_care_query(keyword: str) -> bool:
    """检查是否为消费者护理查询 (非 B2B 核心)。"""
    kw_lower = keyword.lower()
    return any(word in kw_lower for word in _CONSUMER_CARE)


def _has_fact_risk(keyword: str, page_type: str = "") -> bool:
    """检查关键词是否有事实风险。

    风险: 暗示 PU leather 就是 genuine/real leather。
    """
    kw_lower = keyword.lower()
    risky = [
        "pu leather is real leather",
        "pu leather is genuine",
        "pu leather genuine leather",
        "pu leather real",
        "real pu leather",
    ]
    for r in risky:
        if r in kw_lower:
            return True
    return False


def _normalize_fact_risk_keyword(keyword: str) -> tuple[str, str, str]:
    """事实风险关键词改写为安全的 comparison 或 faq。

    Returns:
        (safe_keyword, safe_page_type, safe_title)
    """
    kw_lower = keyword.lower().strip()
    for pattern, safe_kw, safe_type, safe_title in _FACT_RISK_PATTERNS:
        if re.search(pattern, kw_lower):
            return safe_kw, safe_type, safe_title

    # 通用 fallback
    if "real leather" in kw_lower or "genuine leather" in kw_lower:
        return "pu leather vs genuine leather", "comparison", \
               "PU Leather vs Genuine Leather: Key Differences for B2B Buyers"

    return keyword, "article", keyword.title()


def _rewrite_risky_keyword_to_safe_page(keyword: str) -> dict | None:
    """将风险关键词改写为安全页面信息。

    Returns:
        {"primary_keyword": ..., "page_type": ..., "title": ..., "slug": ...} or None
    """
    if not _has_fact_risk(keyword):
        return None

    safe_kw, safe_type, safe_title = _normalize_fact_risk_keyword(keyword)
    return {
        "primary_keyword": safe_kw,
        "page_type": safe_type,
        "title": safe_title,
        "slug": _make_slug(safe_kw),
    }


# ── Semantic Cluster Assignment ───────────────────────


def _assign_semantic_cluster(kw: Keyword) -> str:
    """根据关键词分配到语义 cluster。返回 cluster_name。"""
    kw_lower = kw.keyword.lower()
    best_cluster = None
    best_boost = 0

    for cname, _ptype, match_words, boost in _CLUSTER_RULES:
        for mw in match_words:
            if mw in kw_lower:
                if boost > best_boost:
                    best_boost = boost
                    best_cluster = cname
                break  # 每个 cluster 只检查第一个匹配

    if best_cluster:
        return best_cluster

    # 按 intent fallback
    intent_cluster_map = {
        "comparison": "comparison",
        "faq": "faq-questions",
        "product": "supplier-commercial",
        "category": "product-category",
        "guide": "guide-basics",
        "commercial": "supplier-commercial",
        "transactional": "supplier-commercial",
        "informational": "guide-basics",
    }
    return intent_cluster_map.get(kw.intent, "guide-basics")


def _cluster_name_to_page_type(cname: str) -> str:
    """cluster name → 默认 page_type。"""
    for cn, pt, _mw, _b in _CLUSTER_RULES:
        if cn == cname:
            return pt
    return "article"


# ── Topic Clustering ──────────────────────────────────


def cluster_keywords(keywords: list[Keyword]) -> list[Topic]:
    """关键词聚类: 语义 cluster + intent 合并。

    Args:
        keywords: Keyword 对象列表

    Returns:
        Topic 对象列表 (每个 semantic cluster 最多 1 个 Topic)
    """
    if not keywords:
        return []

    # 按语义 cluster 分组
    by_cluster = defaultdict(list)
    for kw in keywords:
        cname = _assign_semantic_cluster(kw)
        kw.cluster_id = cname
        by_cluster[cname].append(kw)

    topics = []
    tid = 0

    for cname in _CLUSTER_ORDER:
        kw_list = by_cluster.get(cname, [])
        if not kw_list:
            continue

        # 按 priority 降序,取 top keywords
        kw_list.sort(key=lambda k: k.priority, reverse=True)
        primary_kw = _select_primary_keyword(kw_list, cname)

        tid += 1
        page_type = _cluster_name_to_page_type(cname)
        kw_texts = [k.keyword for k in kw_list]

        topics.append(Topic(
            id=f"topic-{tid:03d}",
            name=_generate_topic_name(cname, primary_kw),
            intent=_cluster_intent(cname),
            keywords=kw_texts,
            priority=sum(k.priority for k in kw_list),
            page_type=page_type,
            pillar_keyword=primary_kw,
        ))

    # 处理未分类的 cluster
    for cname, kw_list in by_cluster.items():
        if cname in _CLUSTER_ORDER:
            continue
        if not kw_list:
            continue
        kw_list.sort(key=lambda k: k.priority, reverse=True)
        primary_kw = kw_list[0].keyword
        tid += 1
        topics.append(Topic(
            id=f"topic-{tid:03d}",
            name=primary_kw,
            intent=kw_list[0].intent,
            keywords=[k.keyword for k in kw_list],
            priority=sum(k.priority for k in kw_list),
            page_type=map_topic_to_page_type(kw_list[0].intent, primary_kw),
            pillar_keyword=primary_kw,
        ))

    topics.sort(key=lambda t: t.priority, reverse=True)
    return topics


_CLUSTER_ORDER = [
    "guide-basics", "comparison", "applications",
    "supplier-commercial", "durability-safety",
    "faq-questions", "product-category", "consumer-care",
]


def _cluster_intent(cname: str) -> str:
    return {
        "guide-basics": "guide",
        "comparison": "comparison",
        "applications": "informational",
        "supplier-commercial": "commercial",
        "durability-safety": "faq",
        "faq-questions": "faq",
        "product-category": "category",
        "consumer-care": "faq",
    }.get(cname, "informational")


def _generate_topic_name(cname: str, primary_kw: str) -> str:
    """从 cluster 和 primary keyword 生成有意义的 topic name。"""
    names = {
        "guide-basics": primary_kw,
        "comparison": primary_kw,
        "applications": primary_kw,
        "supplier-commercial": primary_kw,
        "durability-safety": primary_kw,
        "faq-questions": primary_kw,
        "product-category": primary_kw,
    }
    return names.get(cname, primary_kw)


def _select_primary_keyword(kw_list: list[Keyword], cname: str) -> str:
    """为 cluster 选择最佳 primary keyword。"""
    if not kw_list:
        return ""

    if cname == "guide-basics":
        # 优先: 包含 guide/overview/what is 的关键词
        for kw in kw_list:
            kl = kw.keyword.lower()
            if any(w in kl for w in ("guide", "complete", "overview", "what is", "introduction")):
                return kw.keyword
        # 其次: 行业核心词本身(最短的)
        return min(kw_list, key=lambda k: len(k.keyword)).keyword

    # 其他 cluster: 取 priority 最高
    return kw_list[0].keyword


# ── Page Type Mapping ─────────────────────────────────


PAGE_TYPE_MAP = {
    "informational": "article",
    "comparison": "comparison",
    "faq": "faq",
    "product": "product",
    "category": "category",
    "guide": "guide",
    "application": "application",
    "commercial": "category",
    "transactional": "product",
}


def map_topic_to_page_type(intent: str, primary_keyword: str = "") -> str:
    """将 intent 映射为 page_type。特殊关键词可能覆盖。"""
    kw_lower = primary_keyword.lower()
    if any(w in kw_lower for w in ("guide", "overview", "complete", "ultimate", "introduction")):
        return "guide"
    return PAGE_TYPE_MAP.get(intent, "article")


# ── Page Allocation ───────────────────────────────────


def allocate_pages(topics: list[Topic], min_pages: int = 8,
                   max_pages: int = 12) -> list[PagePlan]:
    """从 Topic 列表分配页面 (Phase 3.2: B2B MVP 组合)。

    B2B MVP 组合:
    - 1 guide/pillar
    - 2 comparison
    - 2 application
    - 1 product/supplier
    - 1 faq
    - 1 article/category

    规则:
    - slug/title 从 primary_keyword 生成
    - 事实风险关键词被改写为 comparison/faq
    - consumer care 降级但不删除 (最多 1 个)
    - B2B 评分高的优先
    """
    if not topics:
        return []

    pages = []
    seen_slugs = set()
    seen_pks = set()

    # ── 1. 事实风险预处理: 改写 topics 中的风险关键词 ──
    for t in topics:
        safe = _rewrite_risky_keyword_to_safe_page(t.pillar_keyword or "")
        if safe:
            t.pillar_keyword = safe["primary_keyword"]
            t.page_type = safe["page_type"]
            if t.keywords:
                t.keywords[0] = safe["primary_keyword"]

    # ── 2. B2B 评分排序 ──
    for t in topics:
        b2b_score = _score_page_candidate(
            t.pillar_keyword or "", t.intent,
            _assign_semantic_cluster(Keyword(keyword=t.pillar_keyword or "", intent=t.intent))
        )
        t.priority += b2b_score  # 叠加 B2B 分数

    # ── 3. 选择 pillar ──
    pillar = _select_best_pillar(topics)
    pillar.page_type = "guide"

    pk = pillar.pillar_keyword or (pillar.keywords[0] if pillar.keywords else "")
    pk = _safe_keyword(pk)
    slug = _unique_slug(_make_slug(pk), seen_slugs)
    seen_slugs.add(slug); seen_pks.add(pk)

    pages.append(PagePlan(
        slug=slug,
        title=_generate_title(pk, "guide", "B2B Buyers"),
        page_type="guide",
        primary_keyword=pk,
        secondary_keywords=pillar.keywords[1:5] if len(pillar.keywords) > 1 else [],
        intent=pillar.intent,
        cluster_id=pillar.id,
        parent_slug="",
        suggested_sections=["Overview", "Key Specifications", "Applications", "Buying Guide"],
        internal_links=[],
    ))

    # ── 4. B2B MVP 类型配额 ──
    # 必须类型 (按顺序分配)
    mvp_quotas = [
        ("comparison", 2),
        ("application", 2),
        ("product", 1),
        ("faq", 1),
        ("category", 1),
        ("article", 3),
    ]

    # consumer care 配额: 最多 1 个,且只在 pages >= min_pages 后才考虑
    consumer_care_quota = 1

    remaining = [t for t in topics if t.id != pillar.id]
    remaining.sort(key=lambda t: t.priority, reverse=True)

    # 第一轮: 按类型配额分配
    for t in remaining:
        if len(pages) >= max_pages:
            break

        pt = t.page_type

        # consumer care 特殊处理: 降级, 只有在有剩余配额时才考虑
        is_consumer = _is_consumer_care_query(t.pillar_keyword or "")
        if is_consumer:
            if consumer_care_quota <= 0:
                continue
            # 即使分配 consumer care,page_type 改为 faq
            pt = "faq"

        # 检查类型配额
        quota_hit = False
        for qtype, qcount in mvp_quotas:
            if pt == qtype and qcount > 0:
                quota_hit = True
                break
        if not quota_hit and len(pages) >= min_pages:
            continue

        pk = t.pillar_keyword or (t.keywords[0] if t.keywords else "")
        if not pk or pk.strip() == "":
            continue
        pk = _safe_keyword(pk)
        if pk in seen_pks:
            continue

        slug = _unique_slug(_make_slug(pk), seen_slugs)
        seen_slugs.add(slug); seen_pks.add(pk)

        # 扣除配额
        if is_consumer:
            consumer_care_quota -= 1
        for i, (qtype, qcount) in enumerate(mvp_quotas):
            if pt == qtype:
                mvp_quotas[i] = (qtype, qcount - 1)
                break

        pages.append(PagePlan(
            slug=slug,
            title=_generate_title(pk, pt, "B2B Buyers"),
            page_type=pt,
            primary_keyword=pk,
            secondary_keywords=t.keywords[1:4] if len(t.keywords) > 1 else [],
            intent=t.intent,
            cluster_id=t.id,
            parent_slug=pages[0].slug if pages else "",
            suggested_sections=_suggest_sections(t.intent, pt),
            internal_links=[],
        ))

    # ── 5. 如果不够 min_pages 或类型配额未满,从 secondary keywords 生成额外页 ──
    _fill_from_secondary_keywords(pages, topics, seen_slugs, seen_pks,
                                  mvp_quotas, max_pages)

    # ── 6. 如果不够 min_pages,从剩余中补充 (不限类型配额) ──
    for t in remaining:
        if len(pages) >= min_pages:
            break
        pk = t.pillar_keyword or (t.keywords[0] if t.keywords else "")
        if not pk or pk.strip() == "":
            continue
        pk = _safe_keyword(pk)
        if pk in seen_pks:
            continue
        slug = _unique_slug(_make_slug(pk), seen_slugs)
        seen_slugs.add(slug); seen_pks.add(pk)
        pt = t.page_type
        pages.append(PagePlan(
            slug=slug,
            title=_generate_title(pk, pt, "B2B Buyers"),
            page_type=pt,
            primary_keyword=pk,
            intent=t.intent,
            cluster_id=t.id,
            parent_slug=pages[0].slug if pages else "",
            suggested_sections=_suggest_sections(t.intent, pt),
        ))

    return pages


def _fill_from_secondary_keywords(pages: list, topics: list, seen_slugs: set,
                                  seen_pks: set, mvp_quotas: list, max_pages: int):
    """从 Topic 的 secondary keywords 中提取额外页面,满足类型配额。

    例如 applications cluster 只有 1 个 Topic,但包含 furniture/automotive/bags 三个关键词。
    这里把它们拆成独立页面。
    """
    # 找出还有配额的类型
    needed_types = {qtype for qtype, qcount in mvp_quotas if qcount > 0}
    if not needed_types:
        return

    for t in topics:
        if len(pages) >= max_pages:
            break
        pt = t.page_type
        if pt not in needed_types:
            continue

        # 从 secondary keywords 中找未使用的
        for skw in t.keywords:
            if len(pages) >= max_pages:
                break
            if skw in seen_pks:
                continue
            skw_safe = _safe_keyword(skw)
            if skw_safe in seen_pks:
                continue
            if _has_fact_risk(skw):
                continue

            # 检查类型配额
            quota_remaining = False
            for i, (qtype, qcount) in enumerate(mvp_quotas):
                if pt == qtype and qcount > 0:
                    quota_remaining = True
                    mvp_quotas[i] = (qtype, qcount - 1)
                    break
            if not quota_remaining:
                break

            slug = _unique_slug(_make_slug(skw_safe), seen_slugs)
            seen_slugs.add(slug)
            seen_pks.add(skw_safe)

            pages.append(PagePlan(
                slug=slug,
                title=_generate_title(skw_safe, pt, "B2B Buyers"),
                page_type=pt,
                primary_keyword=skw_safe,
                secondary_keywords=[k for k in t.keywords if k != skw][:3],
                intent=t.intent,
                cluster_id=t.id,
                parent_slug=pages[0].slug if pages else "",
                suggested_sections=_suggest_sections(t.intent, pt),
                internal_links=[],
            ))

            # 更新配额后重新计算 needed_types
            needed_types = {qtype for qtype, qcount in mvp_quotas if qcount > 0}
            if pt not in needed_types:
                break


def _safe_keyword(keyword: str) -> str:
    """确保关键词不含事实风险,有风险则改写。"""
    safe = _rewrite_risky_keyword_to_safe_page(keyword)
    if safe:
        return safe["primary_keyword"]
    return keyword


def _select_best_pillar(topics: list[Topic]) -> Topic:
    """选择最适合作为 pillar 的 topic。

    优先级:
    1. guide-basics cluster
    2. 包含 guide/complete guide/what is 的 keyword
    3. priority 最高的 topic (但不是过窄应用词)
    """
    # 1. guide-basics cluster
    for t in topics:
        if t.id and "guide" in t.id.lower() or t.page_type == "guide":
            return t

    # 2. 包含 guide 关键词
    for t in topics:
        for kw in t.keywords:
            if any(w in kw.lower() for w in ("guide", "complete", "overview", "what is", "introduction")):
                return t

    # 3. priority 最高的非窄 topic
    narrow_words = {"for sofa", "for chair", "for bag", "for shoe"}
    for t in topics:
        pk = (t.pillar_keyword or "").lower()
        if not any(nw in pk for nw in narrow_words):
            return t

    return topics[0]


def _make_slug(text: str) -> str:
    """从文本生成 URL slug (用于 primary_keyword)。"""
    slug = text.strip().lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-{2,}', '-', slug)
    slug = slug.strip('-')[:80]
    # 确保不以数字开头(不利于 SEO)
    if slug and slug[0].isdigit():
        slug = "p-" + slug
    return slug


def _generate_title(primary_keyword: str, page_type: str, audience: str = "B2B Buyers") -> str:
    """从 primary_keyword + page_type 生成自然标题。

    要求:
    - title 不为空
    - title 不等于 slug
    - title 包含 primary keyword 的核心词
    """
    if not primary_keyword or not primary_keyword.strip():
        return "Untitled Page"

    kw = primary_keyword.strip()
    # Capitalize first letter of each word for title case
    kw_title = kw.title() if not kw[0].isupper() else kw

    templates = {
        "guide": [
            f"{kw_title}: The Complete Guide for {audience}",
            f"Complete Guide to {kw_title}",
            f"{kw_title} Guide for {audience}",
        ],
        "pillar": [
            f"{kw_title}: The Complete Guide for {audience}",
            f"Complete Guide to {kw_title}",
        ],
        "comparison": [
            f"{kw_title}: Key Differences for {audience}",
            f"{kw_title} — Which Is Better for Your Needs?",
            f"Comparing {kw_title}",
        ],
        "faq": [
            f"{kw_title} — FAQ for {audience}",
            f"FAQ: {kw_title}",
            f"Everything You Need to Know About {kw_title}",
        ],
        "product": [
            f"{kw_title} — Supplier for {audience}",
            f"{kw_title} for Industrial Applications",
            f"B2B {kw_title} Supplier",
        ],
        "application": [
            f"{kw_title}: Material Guide for {audience}",
            f"{kw_title} for Industrial Use — B2B Material Guide",
            f"B2B Guide: {kw_title}",
        ],
        "category": [
            f"{kw_title}: Applications and Product Categories",
            f"Understanding {kw_title}",
            f"{kw_title} — Types and Applications",
        ],
        "article": [
            f"{kw_title} for {audience}",
            f"Understanding {kw_title}",
            f"{kw_title} — What You Need to Know",
        ],
    }

    options = templates.get(page_type, templates["article"])
    # Pick the first title that's different from a simple slug-like form
    for title in options:
        if title.lower() != kw.lower():
            return title

    return options[0]


def _unique_slug(slug: str, seen: set) -> str:
    """确保 slug 唯一。"""
    if slug not in seen:
        return slug
    for i in range(2, 100):
        candidate = f"{slug}-{i}"
        if candidate not in seen:
            return candidate
    return f"{slug}-{len(seen)}"


def _suggest_sections(intent: str, page_type: str) -> list[str]:
    """根据意图和页型建议页面结构。"""
    templates = {
        "comparison": ["Comparison Overview", "Feature-by-Feature Breakdown", "Pros and Cons", "Cost Comparison", "Which to Choose"],
        "faq": ["Frequently Asked Questions", "Quick Answers", "Detailed Explanations"],
        "product": ["Product Overview", "Specifications", "Applications", "Ordering Information"],
        "category": ["Category Overview", "Types and Grades", "Selection Guide"],
        "guide": ["Overview", "Key Concepts", "Detailed Guide", "Best Practices", "Resources"],
        "application": ["Application Overview", "Material Requirements", "Performance Data", "Case Examples", "Sourcing Tips"],
        "article": ["Introduction", "Main Content", "Key Takeaways", "Related Resources"],
    }
    return templates.get(page_type, templates.get(intent, ["Introduction", "Main Content", "Summary"]))


# ── Link Graph ────────────────────────────────────────


def build_link_graph(pages: list[PagePlan]) -> dict:
    """构建页面链接图(dict adjacency)。

    规则:
    - pillar/guide 页链接到所有 cluster 页
    - cluster 页链接回 pillar + 2-3 个同 cluster 的 sibling
    - 不允许孤儿页
    """
    if not pages:
        return {}

    graph = defaultdict(list)
    slugs = [p.slug for p in pages]
    pillar_slugs = [p.slug for p in pages if p.page_type in ("guide", "pillar")]

    if not pillar_slugs:
        # 如果没有 pillar,把第一个页面当作 pillar
        pillar_slugs = [slugs[0]]

    main_pillar = pillar_slugs[0]

    for page in pages:
        links = []

        # Pillar pages link to all others
        if page.slug in pillar_slugs:
            links = [s for s in slugs if s != page.slug]
        else:
            # Cluster pages link to pillar
            links.append(main_pillar)
            # Link to siblings in same cluster
            siblings = [p.slug for p in pages
                       if p.cluster_id == page.cluster_id and p.slug != page.slug]
            links.extend(siblings[:3])

        # Also add internal_links from page plan
        for il in page.internal_links:
            if il in slugs and il not in links and il != page.slug:
                links.append(il)

        graph[page.slug] = list(dict.fromkeys(links))  # dedup preserving order

    # 验证无孤儿页:所有页面至少被一个其他页面链接
    linked_from = set()
    for src, targets in graph.items():
        for t in targets:
            linked_from.add(t)

    for slug in slugs:
        if slug not in linked_from and slug not in pillar_slugs:
            # 孤儿: 让 pillar 链接它
            graph[main_pillar].append(slug)

    return dict(graph)


# ── Phase 5.1: Competitor Hints Merge ────────────────


def _merge_competitor_hints(pages: list, hints: dict,
                            min_pages: int, max_pages: int) -> bool:
    """把 competitor hints 的 recommended_pages 合并进现有 pages。

    规则:
    - 不重复 slug
    - 不引入事实风险
    - 注入 hints (faq/schema/angle/diff) 到已有页面
    - 新页面优先按 priority_score 和 B2B relevance 选择
    - 注入后重新构建 link_graph
    """
    if not hints:
        return False

    seen_slugs = {p.slug for p in pages}
    seen_pks = {p.primary_keyword.lower() for p in pages}
    applied = False

    # 1. 对已有 page 注入 hints (always do this, even if no new pages)
    for p in pages:
        if hints.get("recommended_sections"):
            p.competitor_gap_hints = list(hints["recommended_sections"][:5])
        if hints.get("recommended_faq"):
            p.recommended_faq = list(hints["recommended_faq"][:3])
        if hints.get("recommended_schema"):
            p.recommended_schema = list(hints["recommended_schema"][:3])
        if hints.get("content_angle"):
            p.content_angle = hints["content_angle"]
        if hints.get("differentiation_points"):
            p.differentiation_points = list(hints["differentiation_points"][:3])
    applied = True

    # 2. 合并新推荐页面 (不超过 max_pages)
    rec_pages = hints.get("recommended_pages", [])
    for rp in rec_pages:
        if len(pages) >= max_pages:
            break
        slug = rp.get("slug", "")
        pk = rp.get("primary_keyword", "")
        if not slug or slug in seen_slugs:
            continue
        if not pk or pk.lower() in seen_pks:
            continue
        if _has_fact_risk(pk):
            safe = _rewrite_risky_keyword_to_safe_page(pk)
            if safe:
                pk = safe["primary_keyword"]
                slug = safe["slug"]
                rp["page_type"] = safe["page_type"]
            else:
                continue

        seen_slugs.add(slug)
        seen_pks.add(pk.lower())
        pt = rp.get("page_type", "article")
        pages.append(PagePlan(
            slug=slug,
            title=rp.get("title", pk.title()),
            page_type=pt,
            primary_keyword=pk,
            competitor_gap_hints=list(hints.get("recommended_sections", [])[:5]),
            recommended_faq=list(hints.get("recommended_faq", [])[:3]),
            recommended_schema=list(hints.get("recommended_schema", [])[:3]),
            content_angle=hints.get("content_angle", ""),
            differentiation_points=list(hints.get("differentiation_points", [])[:3]),
        ))
        applied = True

    return applied


# ── Main Orchestrator ────────────────────────────────


def build_site_blueprint(project_id: int, profile: BusinessProfile,
                         seed_keywords: list[str] = None,
                         min_pages: int = 8,
                         max_pages: int = 12,
                         competitor_hints: dict = None) -> SiteBlueprint:
    """从 BusinessProfile 生成 SiteBlueprint。

    Phase 3.1/5.1: 默认 8-12 页, 语义聚类, 高质量 title/slug。
    支持 competitor_hints 反哺 webpage 候选。

    Pipeline:
    1. expand_seed_keywords() → list[Keyword]
    2. cluster_keywords() → list[Topic] (语义 cluster)
    3. allocate_pages() → list[PagePlan] (8-12 pages, diverse types)
    4. (5.1) merge competitor_hints recommended_pages
    5. build_link_graph() → dict
    6. Return SiteBlueprint
    """
    # 1. 关键词扩展
    keywords = expand_seed_keywords(profile, seed_keywords, limit=210)

    # 2. 语义聚类
    topics = cluster_keywords(keywords)

    # 3. 页面分配 (8-12 pages by default)
    pages = allocate_pages(topics, min_pages=min_pages, max_pages=max_pages)

    # 3b. (Phase 5.1) 合并 competitor hints 推荐页面
    hints_applied = False
    if competitor_hints:
        hints_applied = _merge_competitor_hints(pages, competitor_hints, min_pages, max_pages)

    # 如果页面不够 min_pages, 从关键词直接生成补充页(带 proper title)
    if len(pages) < min_pages:
        seen_pks = {p.primary_keyword for p in pages}
        seen_slugs = {p.slug for p in pages}
        for kw in keywords:
            if len(pages) >= min_pages:
                break
            if kw.keyword in seen_pks:
                continue
            seen_pks.add(kw.keyword)
            slug = _unique_slug(_make_slug(kw.keyword), seen_slugs)
            seen_slugs.add(slug)
            pt = map_topic_to_page_type(kw.intent, kw.keyword)
            pages.append(PagePlan(
                slug=slug,
                title=_generate_title(kw.keyword, pt),
                page_type=pt,
                primary_keyword=kw.keyword,
                intent=kw.intent,
                suggested_sections=_suggest_sections(kw.intent, pt),
            ))

    # 4. 链接图
    link_graph = build_link_graph(pages)

    # 5. 构建返回
    return SiteBlueprint(
        project_id=project_id,
        business_profile=profile,
        keywords=keywords,
        topics=topics,
        pages=pages,
        link_graph=link_graph,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        review_status="approved_for_generation",
        competitor_hints=competitor_hints,
    )
