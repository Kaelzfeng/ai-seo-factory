# -*- coding: utf-8 -*-
"""lib/intent_engine.py · Phase 9.3.8: Generic Conversational Intent Engine

Pure-Python deterministic intent slot extraction and merge.
No LLM, no DB, no HTTP — unit-testable in isolation.

IntentState is a plain dict (not a class) for JSON serialization compatibility.
"""

import re

# ═══════════════════════════════════════════════════════
# Phase 9.3.9: Open-vocabulary product extraction
# ═══════════════════════════════════════════════════════

# Regex patterns for extracting product phrase from natural language.
# Group 1 = the product phrase X.
_PRODUCT_EXTRACTION_PATTERNS = [
    # Chinese patterns (X = product)
    r"帮(?:我|忙)(?:做|制作|生成|弄|建|搭建|创建一个?)\s*(?:一个|个)?\s*(?:卖|关于|面向海外买家的)?\s*(.+?)(?:的)?\s*(?:网站|站|出口站|外贸站|批发网站|B2B\s*网站|SEO\s*页面|英文站|日语站|德语站|法语站|西语站|中文站|韩语站)",
    r"(?:做|制作|生成|弄|建|搭建|创建一个?)\s*(?:一个|个)?\s*(?:卖|关于)?\s*(.+?)(?:的)?\s*(?:出口站|外贸站|批发网站|B2B\s*网站|SEO\s*页面|英文站|日语站|德语站|法语站|西语站|中文站)",
    r"(?:做|制作|生成|弄)\s*(?:一个|个)?\s*(.+?)(?:的)?\s*(?:网站|站|页面|内容页面|内容站)",
    r"(?:我要|我想|帮我|帮忙)\s*(?:做|制作|生成|弄|建)\s*(?:一个|个)?\s*(.+?)(?:的)?\s*(?:站|网站|页面|内容)",
    r"生产[/\s]*出口[/\s]*批发\s*(.+)",
    r"出口[/\s]*批发[/\s]*(.+)",
    r"做\s*(.+?)\s*(?:的)?\s*(?:出口|外贸|外销|海外|B2B)",
    r"卖\s*(.+?)\s*(?:的)?\s*(?:网站|站|英文站)",
    # "关于X的网站"
    r"关于\s*(.+?)\s*(?:的)?\s*(?:网站|站|页面|内容)",
    # "面向海外买家的 X 站点"
    r"面向(?:海外|国外|国际)?\s*(?:买家|客户|市场|批发商|经销商)?\s*(?:的)?\s*(.+?)\s*(?:网站|站|站点|页面|内容)",
    # "X 出口站", "X 外贸站", "X 网站", "X SEO 页面" (X followed by site type)
    r"^(.+?)\s*(?:出口站|外贸站|批发网站|英文站|外贸网站|B2B\s*网站|SEO\s*页面|出口网站|外销站|海外站)$",
    r"(.+?)\s*(?:的)?\s*(?:出口站|外贸站|批发网站|英文站|外贸网站|B2B\s*网站)\b",
    # "X SEO 页面"
    r"(.+?)\s*SEO\s*页面",
    # "X<language><site_type>": "X西语B2B网站", "X英文站", "X日语外贸站"
    r"(.+?)(?:英语|英文|日语|日文|德语|德文|法语|法文|韩语|韩文|西班牙语|西语|中文|汉语|Portuguese|Spanish|French|German|Japanese|Korean|Arabic)(?:B2B|b2b)?(?:\s*网站|\s*外贸站|\s*出口站|\s*站)\b",
    # English patterns
    r"(?:create|build|make|generate)\s+(?:a|an|the)?\s*(?:B2B\s+)?(?:export\s+)?(?:website|site|SEO\s+pages?)\s+(?:for|about)\s+(.+)",
    r"(?:sell|export)\s+(.+?)\s+to\s+(?:overseas\s+)?(?:buyers|wholesalers|distributors)",
    r"(.+?)\s+(?:export|B2B|wholesale|foreign trade)\s+(?:site|website)",
    r"make\s+(?:a|an|the)?\s+(?:B2B\s+)?(?:export\s+)?(?:site|website)\s+(?:for|about)\s+(.+)",
    # "generate SEO pages for X, target Y"
    r"(?:generate|create)\s+SEO\s+pages?\s+for\s+(.+?)(?:,|\.|$)",
    # Bare product names (single message, 2-8 Chinese chars or multi-word English)
    r"^([一-鿿]{2,8})$",
    r"^([a-zA-Z][a-zA-Z\s\-]{2,40})$",
    # "X 英文站", "X 外贸站", "X B2B网站" — product followed by site type without separator
    r"(.+?)\s*(?:英文站|外贸站|日语站|德语站|法语站|西语站|中文站|韩语站|B2B\s*网站|出口网站|外贸网站)\b",
    # Product followed by known language keyword: "X 西班牙语", "X English"
    r"^(.+?)\s+(?:英语|英文|日语|日文|德语|德文|法语|法文|韩语|韩文|西班牙语|西语|中文|汉语|葡萄牙语|俄语|阿拉伯语|越南语|泰语|印尼语|意大利语|荷兰语|土耳其语|波兰语|马来语|English|Japanese|Korean|German|French|Spanish|Portuguese|Russian|Arabic|Vietnamese|Thai|Indonesian|Italian|Dutch|Turkish|Polish|Chinese|Malay)\b",
]

# Words that should NOT be considered as product even if matched by regex
_PRODUCT_STOP_WORDS = {
    "一个", "新的", "自己的", "这个", "那个", "我的", "你的",
    "这个产品", "产品", "the", "a", "an", "my", "our",
    "做网站", "做站", "建站", "生成网站", "网站", "站",
}

# Product-like words that are actually markets → reject as product
_MARKET_LIKE_WORDS = {
    "日本", "日本市场", "美国", "美国市场", "欧洲", "欧洲市场",
    "德国", "德国市场", "英国", "英国市场", "法国", "法国市场",
    "加拿大", "澳大利亚", "澳洲", "东南亚", "中东", "非洲", "南美", "北美",
    "全球", "海外", "墨西哥", "巴西", "印度", "韩国", "俄罗斯",
    "Japan", "USA", "Europe", "Germany", "UK", "Canada", "Australia",
    "global", "Brazil", "Mexico",
}

# ═══════════════════════════════════════════════════════
# Slot extraction keyword maps (kept as fallback)
# ═══════════════════════════════════════════════════════

def _best_match(text, mapping, use_regex=False):
    """Return the first (value) from mapping whose pattern matches text.
    Prefer longer patterns (more specific matches)."""
    matches = []
    for item in mapping:
        pat = item[0]
        if use_regex:
            if re.search(r'\b' + re.escape(pat) + r'\b', text, re.IGNORECASE):
                matches.append((len(pat), item[1:]))
        else:
            if pat in text:
                matches.append((len(pat), item[1:]))
    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[0][1]
    return None


# Chinese product/industry keywords → (product, industry)
_CN_PRODUCT_MAP = [
    # (pattern, product, industry)
    ("五金工具", "五金工具", "hardware tools"),
    ("铁锤", "铁锤", "hardware tools"),
    ("锤子", "锤子", "hardware tools"),
    ("扳手", "扳手", "hardware tools"),
    ("螺丝刀", "螺丝刀", "hardware tools"),
    ("手工具", "手工具", "hardware tools"),
    ("电动工具", "电动工具", "power tools"),
    ("家具", "家具", "furniture"),
    ("沙发", "沙发", "furniture"),
    ("桌子", "桌子", "furniture"),
    ("椅子", "椅子", "furniture"),
    ("床垫", "床垫", "furniture"),
    ("服装", "服装", "apparel"),
    ("衣服", "衣服", "apparel"),
    ("鞋", "鞋", "footwear"),
    ("包", "包", "bags"),
    ("箱包", "箱包", "bags"),
    ("宠物用品", "宠物用品", "pet supplies"),
    ("宠物食品", "宠物食品", "pet supplies"),
    ("猫粮", "猫粮", "pet supplies"),
    ("狗粮", "狗粮", "pet supplies"),
    ("汽车配件", "汽车配件", "auto parts"),
    ("汽车零部件", "汽车零部件", "auto parts"),
    ("电子产品", "电子产品", "electronics"),
    ("手机配件", "手机配件", "electronics"),
    ("LED", "LED灯", "lighting"),
    ("灯具", "灯具", "lighting"),
    ("化妆品", "化妆品", "beauty"),
    ("护肤品", "护肤品", "beauty"),
    ("玩具", "玩具", "toys"),
    ("运动器材", "运动器材", "sports equipment"),
    ("健身器材", "健身器材", "sports equipment"),
    ("包装材料", "包装材料", "packaging"),
    ("食品", "食品", "food"),
    ("茶叶", "茶叶", "tea"),
    ("咖啡", "咖啡", "coffee"),
    ("化工", "化工产品", "chemicals"),
    ("机械", "机械", "machinery"),
    ("医疗器材", "医疗器材", "medical devices"),
    ("医疗器械", "医疗器械", "medical devices"),
    ("SaaS", "SaaS平台", "software"),
    ("软件", "软件", "software"),
    ("皮革", "皮革", "leather"),
    ("PU皮革", "PU皮革", "PU leather"),
    ("面料", "面料", "textiles"),
    ("纺织品", "纺织品", "textiles"),
]

# English product/industry keywords → (product, industry)
_EN_PRODUCT_MAP = [
    ("hardware tools", "Hardware Tools", "hardware tools"),
    ("hammer", "Hammer", "hardware tools"),
    ("wrench", "Wrench", "hardware tools"),
    ("power tools", "Power Tools", "power tools"),
    ("furniture", "Furniture", "furniture"),
    ("sofa", "Sofa", "furniture"),
    ("apparel", "Apparel", "apparel"),
    ("clothing", "Clothing", "apparel"),
    ("garment", "Garment", "apparel"),
    ("footwear", "Footwear", "footwear"),
    ("shoes", "Shoes", "footwear"),
    ("bags", "Bags", "bags"),
    ("leather", "Leather", "leather"),
    ("PU leather", "PU Leather", "PU leather"),
    ("pet supplies", "Pet Supplies", "pet supplies"),
    ("pet food", "Pet Food", "pet supplies"),
    ("auto parts", "Auto Parts", "auto parts"),
    ("car parts", "Car Parts", "auto parts"),
    ("electronics", "Electronics", "electronics"),
    ("beauty", "Beauty", "beauty"),
    ("cosmetics", "Cosmetics", "beauty"),
    ("skincare", "Skincare", "beauty"),
    ("toys", "Toys", "toys"),
    ("sports equipment", "Sports Equipment", "sports equipment"),
    ("packaging", "Packaging", "packaging"),
    ("food", "Food", "food"),
    ("tea", "Tea", "tea"),
    ("coffee", "Coffee", "coffee"),
    ("chemicals", "Chemicals", "chemicals"),
    ("machinery", "Machinery", "machinery"),
    ("medical devices", "Medical Devices", "medical devices"),
    ("textiles", "Textiles", "textiles"),
    ("lighting", "Lighting", "lighting"),
    ("LED", "LED", "lighting"),
]

# Audience detection
_CN_AUDIENCE_MAP = [
    ("海外批发商", "海外批发商"),
    ("批发商", "批发商"),
    ("经销商", "经销商"),
    ("代理商", "代理商"),
    ("分销商", "分销商"),
    ("零售商", "零售商"),
    ("进口商", "进口商"),
    ("B2B企业", "B2B企业"),
    ("B2B客户", "B2B客户"),
    ("B2B买家", "B2B买家"),
    ("终端消费者", "终端消费者"),
    ("消费者", "消费者"),
    ("出口", "出口商/buyers"),
    ("外贸", "外贸客户"),
    ("b2b", "B2B buyers"),
    ("wholesale", "Wholesale buyers"),
    ("distributor", "Distributors"),
    ("dealer", "Dealers"),
    ("importer", "Importers"),
    ("retailer", "Retailers"),
    ("buyer", "Buyers"),
    ("manufacturer", "Manufacturers"),
]

_EN_AUDIENCE_MAP = [
    ("B2B", "B2B buyers"),
    ("b2b", "B2B buyers"),
    ("wholesale", "Wholesale buyers"),
    ("wholesaler", "Wholesale buyers"),
    ("distributor", "Distributors"),
    ("dealer", "Dealers"),
    ("importer", "Importers"),
    ("retailer", "Retailers"),
    ("buyer", "Buyers"),
    ("manufacturer", "Manufacturers"),
]

# Market detection
_CN_MARKET_MAP = [
    ("日本", "日本"),
    ("美国", "美国"),
    ("欧洲", "欧洲"),
    ("德国", "德国"),
    ("英国", "英国"),
    ("法国", "法国"),
    ("加拿大", "加拿大"),
    ("澳大利亚", "澳大利亚"),
    ("澳洲", "澳大利亚"),
    ("东南亚", "东南亚"),
    ("中东", "中东"),
    ("非洲", "非洲"),
    ("南美", "南美"),
    ("北美", "北美"),
    ("全球", "全球"),
    ("海外", "海外"),
    ("墨西哥", "墨西哥"),
    ("巴西", "巴西"),
    ("印度", "印度"),
    ("韩国", "韩国"),
    ("俄罗斯", "俄罗斯"),
]

_EN_MARKET_MAP = [
    ("Japan", "Japan"),
    ("japan", "Japan"),
    ("United States", "USA"),
    ("USA", "USA"),
    ("Europe", "Europe"),
    ("europe", "Europe"),
    ("Germany", "Germany"),
    ("UK", "UK"),
    ("Canada", "Canada"),
    ("Australia", "Australia"),
    ("global", "global"),
    ("Brazil", "Brazil"),
    ("Mexico", "Mexico"),
]

# Language detection
_CN_LANG_MAP = [
    ("英语", "English"),
    ("英文", "English"),
    ("日语", "Japanese"),
    ("日文", "Japanese"),
    ("中文", "Chinese"),
    ("汉语", "Chinese"),
    ("韩语", "Korean"),
    ("韩文", "Korean"),
    ("西班牙语", "Spanish"),
    ("西语", "Spanish"),
    ("法语", "French"),
    ("法文", "French"),
    ("德语", "German"),
    ("德文", "German"),
    ("俄语", "Russian"),
    ("阿拉伯语", "Arabic"),
]

_EN_LANG_MAP = [
    ("english", "English"),
    ("japanese", "Japanese"),
    ("chinese", "Chinese"),
    ("korean", "Korean"),
    ("spanish", "Spanish"),
    ("french", "French"),
    ("german", "German"),
    ("russian", "Russian"),
    ("arabic", "Arabic"),
]

# Market short codes (word-boundary match for standalone codes like "US", "JP")
_MARKET_SHORT_CODES = {
    "US": "USA", "us": "USA",
    "U.S.": "USA", "u.s.": "USA",
    "JP": "Japan", "jp": "Japan",
    "DE": "Germany", "de": "Germany",
    "FR": "France", "fr": "France",
    "UK": "UK", "uk": "UK",
    "BR": "Brazil", "br": "Brazil",
    "MX": "Mexico", "mx": "Mexico",
    "EU": "Europe", "eu": "Europe",
}

# Goal detection
_GOAL_KEYWORDS = [
    "做网站", "生成网站", "建网站", "创建网站",
    "做站", "建站", "生成页面", "SEO", "seo",
    "内容页面", "内容站", "WordPress", "wordpress",
    "generate website", "build website", "create website",
    "generate site", "build site", "make website",
    "export site", "B2B site", "b2b site",
]


# ═══════════════════════════════════════════════════════
# Core functions
# ═══════════════════════════════════════════════════════

def _extract_product_phrase(text):
    """Try to extract a product phrase from natural language using regex patterns.

    Returns (product_name, industry_name) or (None, None) if nothing found.
    The product_name is the raw extracted phrase; industry is inferred or None.
    """
    t = text.strip()
    if not t:
        return (None, None)

    for pat in _PRODUCT_EXTRACTION_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().rstrip(".,;，。；")
            # Filter stop words and very short matches
            if not raw or raw.lower() in _PRODUCT_STOP_WORDS:
                continue
            if len(raw) < 1:
                continue
            # Strip site-type words from the end of the product phrase
            raw = re.sub(r'\s*(?:的|之)?\s*(?:英文|中文|日语|德语|法语|韩语|西语|西班牙语)?\s*(?:B2B|b2b)?\s*(?:出口|外贸|批发|零售|网站|站|页面)?\s*$', '', raw).strip()
            # Also strip leading site-type words
            raw = re.sub(r'^\s*(?:卖|出口|批发|关于|面向|\S*站的)\s*', '', raw).strip()
            if not raw or len(raw) < 1 or raw.lower() in _PRODUCT_STOP_WORDS:
                continue
            # Reject words that look like markets or audience descriptors
            if raw in _MARKET_LIKE_WORDS or raw.lower() in _MARKET_LIKE_WORDS:
                continue
            if raw.lower() in ("wholesale buyers", "wholesale", "distributors", "dealers",
                               "importers", "retailers", "buyers", "distributor", "dealer",
                               "importer", "retailer", "b2b buyers", "B2B buyers"):
                continue
            return (raw, None)

    return (None, None)


def product_display_name(intent):
    """Return a human-readable product name for titles, never None.

    Priority: product > product_phrase > industry > "Product"
    """
    if not intent:
        return "Product"
    name = intent.get("product") or intent.get("product_phrase") or intent.get("industry")
    if name and str(name).strip():
        return str(name).strip()
    return "Product"


def empty_intent():
    """Return a fresh IntentState."""
    return {
        "product": None,
        "industry": None,
        "audience": None,
        "market": None,
        "language": None,
        "goal": None,
        "tone": None,
        "page_count": None,
        "asked_slots": [],
    }


def _detect_overrides(message):
    """Return dict of {slot_key: new_value} for explicit overrides in message."""
    overrides = {}
    text = message.strip()

    # Pattern: "改成X", "换成X", "改为X" (Chinese)
    m = re.search(r"(?:改成|换成|改为)\s*(.+)", text)
    if m:
        target = m.group(1).strip()
        # Try language via normalizer first
        from lib.language_normalizer import normalize as _norm_lang
        for word in target.replace("，", " ").replace(",", " ").split():
            r = _norm_lang(word)
            if r.get("language_confidence") != "defaulted":
                overrides["language"] = r["language"]
                break
        # Market
        mkt_match = _best_match(target, _CN_MARKET_MAP)
        if mkt_match:
            overrides["market"] = mkt_match[0]
        # Audience
        aud_match = _best_match(target, _CN_AUDIENCE_MAP)
        if aud_match:
            overrides["audience"] = aud_match[0]
        # Product
        prod_match = _best_match(target, _CN_PRODUCT_MAP)
        if prod_match:
            overrides["product"] = prod_match[0]
            overrides["industry"] = prod_match[1]

    # Pattern: "不是X是Y", "不是X，而是Y"
    m = re.search(r"不是\S+[,，]*(?:而是|是)\s*(.+)", text)
    if m:
        target = m.group(1).strip()
        mkt_match = _best_match(target, _CN_MARKET_MAP)
        if mkt_match:
            overrides["market"] = mkt_match[0]
        lang_match = _best_match(target, _CN_LANG_MAP)
        if lang_match:
            overrides["language"] = lang_match[0]

    # Pattern: "用X语" "用X文"
    m = re.search(r"用(\S+?)(?:语|文)", text)
    if m:
        lang_key = m.group(1) + "语"
        for pat, lang in _CN_LANG_MAP:
            if pat == lang_key:
                overrides["language"] = lang
                break

    # Pattern: "switch to English", "change language to Japanese"
    m = re.search(r"(?:switch|change)\s+(?:to|language\s+to)\s+(\w+)", text, re.IGNORECASE)
    if m:
        target = m.group(1).lower()
        for pat, lang in _EN_LANG_MAP:
            if pat == target:
                overrides["language"] = lang
                break

    return overrides


def merge_intent(previous, user_message):
    """Merge a user message into the previous intent state.

    Returns a NEW intent dict (does not mutate previous).

    Rules:
    - New slots fill gaps (None → value).
    - Explicit overrides replace existing values.
    - Existing filled slots are preserved unless explicitly overridden.
    """
    import copy
    intent = copy.deepcopy(previous) if previous else empty_intent()
    text = user_message.strip()
    if not text:
        return intent

    # 1. Check for explicit overrides first
    overrides = _detect_overrides(text)
    for slot, value in overrides.items():
        intent[slot] = value
    # If only an override (short message with only override pattern), skip normal detection
    if overrides and len(text) <= 15:
        return intent

    # 2. Detect language (Phase 9.3.9: use language_normalizer for full coverage)
    from lib.language_normalizer import extract_from_phrase, normalize as _norm_lang
    phrase_lang = extract_from_phrase(text)
    if phrase_lang and phrase_lang.get("language_confidence") != "defaulted":
        intent["language"] = phrase_lang["language"]
    else:
        # Try normalize on each word — override if clearly a language keyword
        for word in text.split():
            r = _norm_lang(word)
            if r.get("language_confidence") != "defaulted" and r["language"] != "English":
                intent["language"] = r["language"]
                break
        # If still no language, try normalize without requiring non-English
        if intent["language"] is None:
            for word in text.split():
                r = _norm_lang(word)
                if r.get("language_confidence") != "defaulted":
                    intent["language"] = r["language"]
                    break
        # Fall back to keyword matching
        if intent["language"] is None:
            cn_lang = _best_match(text, _CN_LANG_MAP)
            if cn_lang:
                intent["language"] = cn_lang[0]
            else:
                en_lang = _best_match(text, _EN_LANG_MAP, use_regex=True)
                if en_lang:
                    intent["language"] = en_lang[0]

    # 3. Detect market (longest match first; override if message is primarily a market keyword)
    cn_mkt = _best_match(text, _CN_MARKET_MAP)
    if cn_mkt:
        intent["market"] = cn_mkt[0]
    elif intent["market"] is None:
        en_mkt = _best_match(text, _EN_MARKET_MAP, use_regex=True)
        if en_mkt:
            intent["market"] = en_mkt[0]
        else:
            # Try market short codes (US, JP, DE, etc.) with word boundary
            for code, name in _MARKET_SHORT_CODES.items():
                if re.search(r'\b' + re.escape(code) + r'\b', text):
                    intent["market"] = name
                    break

    # 4. Detect audience (longest match first; always update if clearly stated)
    cn_aud = _best_match(text, _CN_AUDIENCE_MAP)
    if cn_aud:
        intent["audience"] = cn_aud[0]
    elif intent["audience"] is None:
        en_aud = _best_match(text, _EN_AUDIENCE_MAP, use_regex=True)
        if en_aud:
            intent["audience"] = en_aud[0]
    # Also detect standalone B2B/b2b as B2B audience signal
    if intent["audience"] is None:
        if re.search(r'(?<![a-zA-Z])B2B(?![a-zA-Z])', text) or re.search(r'(?<![a-zA-Z])b2b(?![a-zA-Z])', text):
            intent["audience"] = "B2B buyers"

    # 5. Detect product/industry — Phase 9.3.9: keyword maps first, then open-vocabulary regex
    if intent["product"] is None and intent["industry"] is None:
        # Try keyword maps first (more specific for known products)
        cn_match = _best_match(text, _CN_PRODUCT_MAP)
        if cn_match:
            intent["product"], intent["industry"] = cn_match
        else:
            en_match = _best_match(text, _EN_PRODUCT_MAP, use_regex=True)
            if en_match:
                intent["product"], intent["industry"] = en_match
            else:
                # Fall back to open-vocabulary regex extraction
                prod, ind = _extract_product_phrase(text)
                if prod:
                    intent["product"] = prod
                    if ind:
                        intent["industry"] = ind

    # 6. Detect goal
    if intent["goal"] is None:
        for kw in _GOAL_KEYWORDS:
            if kw.lower() in text.lower():
                intent["goal"] = "generate website"
                break
        # Auto-infer if user clearly wants a site
        if intent["goal"] is None:
            site_signals = ["网站", "站", "website", "site", "生成", "页面", "内容"]
            if any(s in text for s in site_signals):
                intent["goal"] = "generate website"

    # 7. Detect tone
    if intent["tone"] is None:
        if "professional" in text.lower() or "专业" in text:
            intent["tone"] = "professional"
        elif "B2B" in text or "b2b" in text:
            intent["tone"] = "B2B"
        elif "premium" in text.lower() or "高端" in text:
            intent["tone"] = "premium"
        elif "conversion" in text.lower() or "转化" in text:
            intent["tone"] = "conversion"

    return intent


def is_intent_ready(intent):
    """Return True if enough slots are filled to start generation.

    Ready when:
    - product OR industry exists
    - audience OR market exists
    - language exists (or defaults to English)
    - goal exists (or infers to generate website)
    """
    if not intent:
        return False

    product = intent.get("product") or intent.get("product_phrase") or intent.get("industry")
    has_product_or_industry = bool(product and str(product).strip())
    has_audience_or_market = bool(intent.get("audience") or intent.get("market"))
    has_language = bool(intent.get("language"))
    has_goal = bool(intent.get("goal"))

    # Language defaults to English
    if not has_language and (has_product_or_industry and has_audience_or_market):
        intent["language"] = "English"
        has_language = True

    # Goal defaults to generate website if user clearly signaled intent
    if not has_goal and has_product_or_industry and has_audience_or_market:
        intent["goal"] = "generate website"
        has_goal = True

    return has_product_or_industry and has_audience_or_market and has_language and has_goal


def get_missing_slots(intent):
    """Return list of slot keys that are still missing and not yet asked."""
    if not intent:
        return ["product", "audience", "market", "language"]

    asked = set(intent.get("asked_slots", []))

    # Priority order for missing slots
    priority = ["product", "industry", "audience", "market", "language"]
    missing = []

    # Product/industry combined — if neither exists, ask for product first
    if not intent.get("product") and not intent.get("industry"):
        if "product" not in asked and "industry" not in asked:
            missing.append("product")

    # Audience
    if not intent.get("audience"):
        if "audience" not in asked:
            missing.append("audience")

    # Market
    if not intent.get("market"):
        if "market" not in asked:
            missing.append("market")

    # Language
    if not intent.get("language"):
        if "language" not in asked:
            missing.append("language")

    return missing


def build_clarification(intent):
    """Build a natural Chinese clarification message for the first missing slot.

    Marks the asked slot in `asked_slots` to prevent repetition.
    Returns (message_text, updated_intent).
    """
    intent = intent or empty_intent()
    missing = get_missing_slots(intent)

    if not missing:
        # All slots addressed but intent still not ready — edge case, try generic
        if "fallback" not in intent.get("asked_slots", []):
            intent.setdefault("asked_slots", []).append("fallback")
            return "请再详细说说你的产品和目标市场，我来继续规划。", intent
        return "请简短描述你的产品和面向的市场。", intent

    slot = missing[0]
    intent.setdefault("asked_slots", []).append(slot)

    messages = {
        "product": "你想为哪一种产品或行业创建网站？给我一个产品名就可以。",
        "industry": "你的产品属于哪个行业？",
        "audience": "主要面向哪类买家：海外批发商、经销商，还是终端消费者？",
        "market": "目标市场是哪里？比如日本、美国、欧洲还是全球？",
        "language": "页面用什么语言？英文、日文还是中文？",
    }

    return messages.get(slot, "请补充更多信息。"), intent
