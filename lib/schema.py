"""lib/schema.py — JSON-LD 结构化数据生成

为每个页面构建恰好一个 <script type="application/ld+json"> 块（单一 @graph）。
按 page["type"] 分派：

    pillar / comparison / application / guide  -> Article  + BreadcrumbList
    faq                                        -> FAQPage  + BreadcrumbList
    product                                    -> Product + Offer + BreadcrumbList

每个 @graph 都附带一个稳定 @id 的 Organization 节点，
让 publisher/seller/author 的 @id 引用可以解析。

设计原则（baked-in，对照 BUILD SPEC §4）：
  - 永不编造 gtin/sku/review/aggregateRating。
  - 永不输出 price:"0" / "Contact us"。
  - markup 必须镜像可见内容。
  - 对缺失字段健壮：所有读取都用 .get(...)，缺则省略对应字段/节点。
  - 永不返回 None —— 未知 type 回退到 Article + BreadcrumbList。
  - JSON 用 json.dumps(ensure_ascii=False, indent=2)，无尾随逗号。

公共签名（pinned，不得偏离）：
    jsonld_for(page, content, site, industry) -> str
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from html import unescape

# 站点默认时区：+08:00（中国/工厂时间），用于 datePublished/dateModified 兜底。
_TZ = timezone(timedelta(hours=8))

# Article headline 上限（Google 推荐 ≤110 字符）。
_HEADLINE_MAX = 110


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _clean(s) -> str:
    """安全转成字符串并去掉首尾空白；None -> ''。"""
    if s is None:
        return ""
    return str(s).strip()


def _truncate(s: str, limit: int) -> str:
    """截断到 limit 字符（含），尽量在词边界断开，不加省略号污染 schema。"""
    s = _clean(s)
    if len(s) <= limit:
        return s
    cut = s[:limit].rstrip()
    # 在最后一个空格处收尾，避免把单词切一半。
    sp = cut.rfind(" ")
    if sp > limit * 0.6:
        cut = cut[:sp].rstrip()
    return cut


def _abs_url(site: str, url_or_slug: str) -> str:
    """把 url/slug 归一成绝对 URL。已是 http(s):// 的原样返回。"""
    site = _clean(site).rstrip("/")
    v = _clean(url_or_slug)
    if not v:
        return f"{site}/"
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return f"{site}/{v.strip('/')}/"


def _lang_short(industry: dict) -> str:
    """把 industry.language（'English' / 'zh-CN' / ...）映射成短码。"""
    lang = _clean((industry or {}).get("language")) or "English"
    low = lang.lower()
    table = {
        "english": "en",
        "chinese": "zh",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "japanese": "ja",
        "korean": "ko",
        "portuguese": "pt",
        "italian": "it",
        "russian": "ru",
        "arabic": "ar",
    }
    if low in table:
        return table[low]
    # 已经是短码或带地区码（en / en-US / zh-CN）的，原样保留。
    if re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?", lang):
        return lang
    return "en"


def _now_iso() -> str:
    return datetime.now(_TZ).replace(microsecond=0).isoformat()


def _date(page: dict, key: str) -> str:
    """从 page 取 ISO 日期；缺失则用当前 +08:00 时间兜底。"""
    v = _clean((page or {}).get(key))
    return v or _now_iso()


def _strip_html_text(html: str) -> str:
    """粗略剥离 HTML 标签得到可见文本（用于 FAQ 兜底解析）。"""
    if not html:
        return ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = unescape(txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


# ---------------------------------------------------------------------------
# 节点构建（pinned internal helpers）
# ---------------------------------------------------------------------------
def _organization_node(site: str, industry: dict) -> dict:
    """稳定 @id="{site}#organization" 的 Organization 节点。

    读取 industry：org_name(回退 name)、url、logo_url、org_description、
    same_as[]、telephone、email、address。缺失字段一律省略。
    """
    industry = industry or {}
    site = _clean(site).rstrip("/")
    name = _clean(industry.get("org_name")) or _clean(industry.get("name")) or site

    node = {
        "@type": "Organization",
        "@id": f"{site}#organization",
        "name": name,
        "url": f"{site}/",
    }

    logo_url = _clean(industry.get("logo_url"))
    if logo_url:
        node["logo"] = {
            "@type": "ImageObject",
            "@id": f"{site}#logo",
            "url": logo_url,
        }
        # image 引用 logo，便于 Google 关联品牌图片。
        node["image"] = {"@id": f"{site}#logo"}

    desc = _clean(industry.get("org_description"))
    if desc:
        node["description"] = desc

    same_as = industry.get("same_as")
    if isinstance(same_as, (list, tuple)):
        cleaned = [_clean(x) for x in same_as if _clean(x)]
        if cleaned:
            node["sameAs"] = cleaned

    tel = _clean(industry.get("telephone"))
    if tel:
        node["telephone"] = tel

    email = _clean(industry.get("email"))
    if email:
        node["email"] = email

    address = industry.get("address")
    if isinstance(address, dict) and address:
        # 透传地址字段（PostalAddress），保留调用方提供的键。
        addr = {"@type": "PostalAddress"}
        for k in ("streetAddress", "addressLocality", "addressRegion",
                  "postalCode", "addressCountry"):
            v = _clean(address.get(k))
            if v:
                addr[k] = v
        if len(addr) > 1:
            node["address"] = addr
    elif _clean(address):
        node["address"] = _clean(address)

    return node


def _breadcrumb_node(page: dict, site: str, industry: dict) -> dict:
    """BreadcrumbList，≥2 个 ListItem。

    pillar:  Home -> {title}
    cluster: Home -> {default_category}@pillar_url -> {title}@url
             （crumb #2 指向 pillar，让面包屑兼作 up-link）
    position 从 1 开始；item 用绝对 URL。
    """
    page = page or {}
    industry = industry or {}
    site = _clean(site).rstrip("/")
    home = f"{site}/"
    title = _clean(page.get("title")) or _clean((page.get("type") or "Page").title())
    page_url = _abs_url(site, page.get("url") or page.get("slug"))
    ptype = _clean(page.get("type")).lower()

    items = [{
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": home,
    }]

    pillar_url = _clean(page.get("pillar_url"))
    if ptype != "pillar" and pillar_url:
        category = _clean(industry.get("default_category")) or "Articles"
        items.append({
            "@type": "ListItem",
            "position": 2,
            "name": category,
            "item": _abs_url(site, pillar_url),
        })
        items.append({
            "@type": "ListItem",
            "position": 3,
            "name": title,
            "item": page_url,
        })
    else:
        # pillar，或缺 pillar_url 的兜底：Home -> {title}
        items.append({
            "@type": "ListItem",
            "position": 2,
            "name": title,
            "item": page_url,
        })

    return {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": items,
    }


def _article_graph(page, content, site, industry) -> list:
    """Article + BreadcrumbList（+ Organization 由顶层注入）。"""
    page = page or {}
    content = content or {}
    industry = industry or {}
    site = _clean(site).rstrip("/")
    url = _abs_url(site, page.get("url") or page.get("slug"))

    headline = _truncate(_clean(content.get("title")) or _clean(page.get("title")),
                         _HEADLINE_MAX)

    article = {
        "@type": "Article",
        "@id": f"{url}#article",
        "headline": headline,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "author": {"@id": f"{site}#organization"},
        "publisher": {"@id": f"{site}#organization"},
        "datePublished": _date(page, "date_published"),
        "dateModified": _date(page, "date_modified"),
        "inLanguage": _lang_short(industry),
    }

    desc = _clean(content.get("meta_description"))
    if desc:
        article["description"] = desc

    img = _clean(page.get("featured_image_url"))
    if img:
        article["image"] = [img]

    kw = _clean(page.get("target_keyword"))
    if kw:
        article["keywords"] = kw

    return [article, _breadcrumb_node(page, site, industry)]


def _extract_faq_pairs(page, content) -> list:
    """得到 [{q,a}, ...]。优先用 page['faq']；否则从 HTML 抽取 <h2>…?</h2>+其后文本。"""
    page = page or {}
    content = content or {}

    faq = page.get("faq")
    pairs = []
    if isinstance(faq, (list, tuple)):
        for it in faq:
            if not isinstance(it, dict):
                continue
            q = _clean(it.get("q"))
            a = _clean(it.get("a"))
            if q and a:
                pairs.append({"q": q, "a": a})
        if len(pairs) >= 2:
            return pairs

    # 兜底：从 HTML 抽取以 '?' 结尾的 <h2>/<h3> 作为问题，其后到下个同级标题的可见文本作为答案。
    html = _clean(content.get("html"))
    if html:
        # 匹配每个标题块及其后续内容，直到下一个 h1-h3 或文档结束。
        blocks = re.split(r"(?i)(<h[1-3][^>]*>.*?</h[1-3]>)", html)
        # blocks 交替：[before, heading, body, heading, body, ...]
        i = 1
        while i < len(blocks) - 1:
            heading_html = blocks[i]
            body_html = blocks[i + 1] if i + 1 < len(blocks) else ""
            q_text = _strip_html_text(heading_html)
            if q_text.endswith("?"):
                a_text = _strip_html_text(body_html)
                if q_text and a_text:
                    pairs.append({"q": q_text, "a": a_text})
            i += 2

    return pairs


def _faq_graph(page, content, site, industry) -> list:
    """FAQPage(≥2 Question) + BreadcrumbList；不足 2 条则回退 Article+Breadcrumb。"""
    page = page or {}
    industry = industry or {}
    site = _clean(site).rstrip("/")
    url = _abs_url(site, page.get("url") or page.get("slug"))

    pairs = _extract_faq_pairs(page, content)
    if len(pairs) < 2:
        # 找不到足够问答 —— 退回 Article + Breadcrumb（spec §4）。
        return _article_graph(page, content, site, industry)

    questions = []
    for it in pairs:
        questions.append({
            "@type": "Question",
            "name": it["q"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": it["a"],
            },
        })

    faq_node = {
        "@type": "FAQPage",
        "@id": f"{url}#faqpage",
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "inLanguage": _lang_short(industry),
        "mainEntity": questions,
    }

    name = _truncate(_clean((content or {}).get("title")) or _clean(page.get("title")),
                     _HEADLINE_MAX)
    if name:
        faq_node["name"] = name

    return [faq_node, _breadcrumb_node(page, site, industry)]


def _product_graph(page, content, site, industry) -> list:
    """Product + Offer + BreadcrumbList。

    - additionalProperty <- page['product_specs'] (PropertyValue{name,value,unitText})
    - sku/mpn 仅在显式提供时输出；永不编造 gtin。
    - 仅当 page 含真实数字价格时才输出 priceSpecification，否则整段省略。
    """
    page = page or {}
    content = content or {}
    industry = industry or {}
    site = _clean(site).rstrip("/")
    url = _abs_url(site, page.get("url") or page.get("slug"))
    org_id = f"{site}#organization"

    name = _truncate(_clean(content.get("title")) or _clean(page.get("title")),
                     _HEADLINE_MAX)

    product = {
        "@type": "Product",
        "@id": f"{url}#product",
        "name": name,
        "url": url,
        "brand": {"@id": org_id},
    }

    desc = _clean(content.get("meta_description"))
    if desc:
        product["description"] = desc

    img = _clean(page.get("featured_image_url"))
    if img:
        product["image"] = [img]

    category = _clean(industry.get("default_category"))
    if category:
        product["category"] = category

    sku = _clean(page.get("sku"))
    if sku:
        product["sku"] = sku
    mpn = _clean(page.get("mpn"))
    if mpn:
        product["mpn"] = mpn

    # 规格 -> additionalProperty
    specs = page.get("product_specs")
    add_props = []
    if isinstance(specs, (list, tuple)):
        for sp in specs:
            if not isinstance(sp, dict):
                continue
            pname = _clean(sp.get("name"))
            pval = _clean(sp.get("value"))
            if not pname or not pval:
                continue
            pv = {"@type": "PropertyValue", "name": pname, "value": pval}
            unit = _clean(sp.get("unitText"))
            if unit:
                pv["unitText"] = unit
            add_props.append(pv)
    if add_props:
        product["additionalProperty"] = add_props

    # Offer：不带价格（除非有真实数字价）。
    offer = {
        "@type": "Offer",
        "@id": f"{url}#offer",
        "url": url,
        "availability": "https://schema.org/InStock",
        "itemCondition": "https://schema.org/NewCondition",
        "businessFunction": "http://purl.org/goodrelations/v1#Sell",
        "seller": {"@id": org_id},
    }

    # 仅在存在真实数字价格时输出 priceSpecification。
    price_raw = page.get("price")
    price_num = None
    if price_raw is not None:
        m = re.search(r"-?\d+(?:[.,]\d+)?", str(price_raw))
        if m:
            try:
                price_num = float(m.group(0).replace(",", "."))
            except ValueError:
                price_num = None
    if price_num is not None and price_num > 0:
        currency = _clean(page.get("currency")) or "USD"
        offer["priceSpecification"] = {
            "@type": "PriceSpecification",
            "price": f"{price_num:g}",
            "priceCurrency": currency,
        }

    product["offers"] = offer

    return [product, _breadcrumb_node(page, site, industry)]


# ---------------------------------------------------------------------------
# 公共入口（pinned signature）
# ---------------------------------------------------------------------------
def jsonld_for(page: dict, content: dict, site: str, industry: dict) -> str:
    """为该页面构建一个完整的 <script type="application/ld+json"> 块。

    见模块 docstring 与 BUILD SPEC §4。永不返回 None：未知 type 回退到
    Article + BreadcrumbList。所有 schema 类型放进单一 @graph。
    """
    page = page or {}
    content = content or {}
    industry = industry or {}
    site = _clean(site).rstrip("/")

    ptype = _clean(page.get("type")).lower()

    if ptype == "faq":
        graph = _faq_graph(page, content, site, industry)
    elif ptype == "product":
        graph = _product_graph(page, content, site, industry)
    else:
        # pillar / comparison / application / guide / 未知 -> Article + Breadcrumb
        graph = _article_graph(page, content, site, industry)

    # Organization 节点放在 @graph 开头，让所有 @id 引用可解析。
    org = _organization_node(site, industry)
    full_graph = [org] + list(graph)

    data = {
        "@context": "https://schema.org",
        "@graph": full_graph,
    }

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{payload}\n</script>'
