"""质量评分（内功层）：确定性、无 LLM 的逐页打分。

这是质量护城河 —— 拦截 AI slop、保证 information gain 与内链闭环。
六个维度合计 100 分，>= PASS_THRESHOLD(70) 即通过。
本模块是 skills/quality-rubric/SKILL.md 的可执行镜像，二者必须保持同步。

签名锁定（不得偏离）：
    score_page(page, content, industry) -> {score, breakdown, issues, passed}
辅助函数（也被锁定，供 app.py / 测试复用）：
    strip_html / word_count / extract_links / count_headings
"""
import re
import html as _htmllib

# 通过阈值：分数 >= 该值即视为通过，是 run.py 唯一检查的门槛。
PASS_THRESHOLD: float = 70.0

# §2 反 AI-slop 黑名单（与 skills/seo-content/SKILL.md 逐字镜像，保持同步）。
# 全部小写、大小写不敏感匹配。
BANNED_PHRASES = [
    "in today's fast-paced world",
    "in today’s fast-paced world",   # 弯引号变体
    "delve into",
    "delve",
    "dive into",
    "comprehensive",
    "it is worth noting",
    "it is important to understand",
    "in conclusion",
    "navigating the complex landscape",
    "unlock",
    "elevate",
    "leverage",
    "robust",
    "seamless",
    "cutting-edge",
]

# specificity（规格信号）正则：数字后面跟单位 / 标准 token，或认证名。
# 命中越多说明文案越具体、越像工厂而非博主。
SPEC_SIGNAL_PATTERNS = [
    r"\d+(?:\.\d+)?\s*mm\b",                       # 毫米厚度
    r"\d+(?:[\.,]\d+)?\s*g/?m[²2]\b",              # GSM 克重 g/m²
    r"\bgsm\b",
    r"\bmartindale\b",
    r"\biso\s*\d+",                                # ISO 标准号
    r"\bastm\b",
    r"\d+(?:\.\d+)?\s*n/?\s*25\s*mm\b",            # N/25mm 剥离力
    r"\bmoq\b",
    r"\d+(?:\.\d+)?\s*%",                          # 百分比
    r"\breach\b",
    r"\brohs\b",
    r"\boeko-?tex\b",
    r"\bwyzenbeek\b",
    r"\bsae\s*j?\d+",
    r"\bgrs\b",
    r"\bprop\s*65\b",
]

# 认证 / 标准 token：用于 "零 slop 且至少出现一个标准" 的奖励判定。
CERT_STANDARD_TOKENS = [
    "iso", "astm", "martindale", "wyzenbeek", "reach", "rohs",
    "oeko-tex", "oeko tex", "sae j", "grs", "prop 65", "sgs",
    "intertek", "bureau veritas", "eurofins",
]

# 被禁的内链锚文本（非描述性 / 裸 URL），命中要扣分。
FORBIDDEN_ANCHORS = ["click here", "read more", "this page", "here", "learn more"]


def strip_html(html: str) -> str:
    """剥离标签，返回可见文本（含基本实体解码、空白归一）。"""
    if not html:
        return ""
    text = str(html)
    # 移除 script / style 整块（含内容），避免 JSON-LD 等污染正文统计。
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    # 其余标签替换为空格，避免相邻词粘连。
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = _htmllib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_count(html: str) -> int:
    """统计可见文本词数（先 strip_html 再按空白切分）。"""
    text = strip_html(html)
    if not text:
        return 0
    return len(text.split())


def extract_links(html: str) -> list:
    """解析所有 <a href>，返回 [{"href": str, "anchor": str}, ...]。解析失败返回 []。"""
    if not html:
        return []
    links = []
    try:
        for m in re.finditer(r"(?is)<a\b([^>]*?)>(.*?)</a>", str(html)):
            attrs, inner = m.group(1), m.group(2)
            href_m = re.search(r"""(?is)\bhref\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))""", attrs)
            href = ""
            if href_m:
                href = href_m.group(2) or href_m.group(3) or href_m.group(4) or ""
            anchor = strip_html(inner)
            links.append({"href": href.strip(), "anchor": anchor})
    except Exception:
        return []
    return links


def count_headings(html: str) -> dict:
    """统计 h1/h2/h3 数量，返回 {"h1": int, "h2": int, "h3": int}。"""
    out = {"h1": 0, "h2": 0, "h3": 0}
    if not html:
        return out
    for level in ("h1", "h2", "h3"):
        out[level] = len(re.findall(r"(?is)<%s[\s>]" % level, str(html)))
    return out


# ----------------------------------------------------------------------------
# 内部辅助
# ----------------------------------------------------------------------------

def _normalize_kw(text: str) -> str:
    """关键词归一化：小写、去标点、压缩空白。"""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9一-鿿\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_in(keyword: str, haystack: str, allow_reorder: bool = True) -> bool:
    """关键词是否出现在 haystack（大小写不敏感，允许少量 token 重排）。"""
    nk = _normalize_kw(keyword)
    nh = _normalize_kw(haystack)
    if not nk:
        return False
    if nk in nh:
        return True
    if allow_reorder:
        # 所有 token 都出现（顺序无关、紧密度不强求）即算命中。
        tokens = [t for t in nk.split() if len(t) > 1]
        if tokens and all(t in nh for t in tokens):
            return True
    return False


def _count_keyword(keyword: str, haystack: str) -> int:
    """统计关键词在文本中出现次数（按整短语，大小写不敏感）。"""
    nk = _normalize_kw(keyword)
    nh = _normalize_kw(haystack)
    if not nk:
        return 0
    return nh.count(nk)


def _normalize_url(url: str) -> str:
    """URL 归一化用于比较：小写、去查询/锚点、去尾部斜杠。"""
    u = (url or "").strip().lower()
    u = u.split("#", 1)[0].split("?", 1)[0]
    return u.rstrip("/")


def _heading_texts(html: str, levels=("h2", "h3")) -> list:
    """取出指定层级标题的可见文本列表。"""
    out = []
    for lvl in levels:
        for m in re.finditer(r"(?is)<%s[^>]*>(.*?)</%s>" % (lvl, lvl), str(html or "")):
            out.append(strip_html(m.group(1)))
    return out


def _has_skipped_heading_level(html: str) -> bool:
    """检测是否出现 h2→h4 之类跳级（h2 之后直接出现 h4/h5/h6 而中间无 h3）。

    简化判定：按出现顺序扫描所有标题层级，若相邻层级从 n 直接跳到 > n+1 则算跳级。
    """
    seq = []
    for m in re.finditer(r"(?is)<h([1-6])[\s>]", str(html or "")):
        seq.append(int(m.group(1)))
    for prev, cur in zip(seq, seq[1:]):
        if cur > prev + 1:
            return True
    return False


# ----------------------------------------------------------------------------
# 主评分函数
# ----------------------------------------------------------------------------

def score_page(page: dict, content: dict, industry: dict) -> dict:
    """确定性地给一页打分（无 LLM 调用，纯输入函数）。

    返回严格形状：
      {"score": float, "breakdown": dict, "issues": list[str], "passed": bool}
    分数 = 六维之和（满分 100），保留 1 位小数；passed = score >= PASS_THRESHOLD。
    本函数对畸形 HTML 不抛异常：解析失败的维度记 0 分并产生一条 issue。
    """
    page = page or {}
    content = content or {}
    industry = industry or {}

    title = str(content.get("title", "") or "")
    meta = str(content.get("meta_description", "") or "")
    html = str(content.get("html", "") or "")
    body_text = strip_html(html)

    target_kw = str(page.get("target_keyword", "") or "")
    page_type = str(page.get("type", "") or "").lower()
    pillar_url = page.get("pillar_url")
    page_url = page.get("url")
    related = page.get("related") or []

    issues = []
    breakdown = {}

    # ---- 维度 1：keyword_usage（满分 15）----
    kw_score = 0.0
    kw_notes = []
    if target_kw:
        if _keyword_in(target_kw, title):
            kw_score += 5
        else:
            issues.append("Target keyword missing from title")
            kw_notes.append("not in title")
        if _keyword_in(target_kw, meta):
            kw_score += 3
        else:
            issues.append("Target keyword missing from meta description")
            kw_notes.append("not in meta")
        # 出现在某个 h2/h3，或正文前 150 词内。
        head_text = " ".join(_heading_texts(html, ("h2", "h3")))
        first_150 = " ".join(body_text.split()[:150])
        if _keyword_in(target_kw, head_text) or _keyword_in(target_kw, first_150):
            kw_score += 4
        else:
            issues.append("Target keyword not in any H2/H3 or first 150 words of body")
            kw_notes.append("not in heading/intro")
        # 正文出现 1-4 次为佳；>6 视为堆砌。
        cnt = _count_keyword(target_kw, body_text)
        if 1 <= cnt <= 4:
            kw_score += 3
        elif cnt == 0:
            issues.append("Target keyword never appears in body")
        elif cnt > 6:
            kw_score -= 3
            issues.append(f"Keyword stuffing: target keyword appears {cnt} times in body (keep 1-4)")
        kw_notes.append(f"body count={cnt}")
    else:
        issues.append("Page has no target_keyword to score against")
    kw_score = max(0.0, min(15.0, kw_score))
    breakdown["keyword_usage"] = {
        "score": round(kw_score, 1), "max": 15.0, "notes": "; ".join(kw_notes) or "ok",
    }

    # ---- 维度 2：structure（满分 20）----
    st_score = 0.0
    st_notes = []
    try:
        h = count_headings(html)
        # 恰好一个 h1。
        if h["h1"] == 1:
            st_score += 5
        else:
            issues.append(f"Found {h['h1']} <h1> (need exactly 1)")
            st_notes.append(f"h1={h['h1']}")
        # >= 3 个 h2。
        if h["h2"] >= 3:
            st_score += 5
        else:
            issues.append(f"Only {h['h2']} H2 found; need >=3 for scannable structure")
            st_notes.append(f"h2={h['h2']}")
        # 不跳级。
        if not _has_skipped_heading_level(html):
            st_score += 3
        else:
            issues.append("Heading levels skip (e.g. h2 -> h4); do not skip levels")
        # 至少一个列表 / 表格。
        if re.search(r"(?is)<(ul|ol|table)[\s>]", html):
            st_score += 4
        else:
            issues.append("No <ul>/<ol>/<table> found; use lists/tables for specs")
        # 至少一个 h2 写成问题（以 ? 结尾）。
        h2_texts = _heading_texts(html, ("h2",))
        if any(t.strip().endswith("?") or t.strip().endswith("？") for t in h2_texts):
            st_score += 3
        else:
            issues.append("No question-style H2 (ending with '?')")
    except Exception:
        st_score = 0.0
        issues.append("Structure parse failed; treated as 0")
    st_score = max(0.0, min(20.0, st_score))
    breakdown["structure"] = {
        "score": round(st_score, 1), "max": 20.0, "notes": "; ".join(st_notes) or "ok",
    }

    # ---- 维度 3：depth_wordcount（满分 20）----
    dp_score = 0.0
    try:
        wc = word_count(html)
        is_pillar = page_type == "pillar"
        if is_pillar:
            target_full = 1800
        else:
            target_full = 900
        if wc >= target_full:
            dp_score = 20.0
        elif wc >= 400:
            # 从 400 词线性缩放到 target_full。
            dp_score = 5.0 + 15.0 * (wc - 400) / float(target_full - 400)
            dp_score = max(5.0, min(20.0, dp_score))
        else:
            # < 400 词硬伤，最多 5 分。
            dp_score = max(0.0, 5.0 * wc / 400.0)
            issues.append(f"Only {wc} words; thin content (<400) will not rank")
        dp_notes = f"words={wc}, target_full={target_full}, pillar={is_pillar}"
    except Exception:
        dp_score = 0.0
        dp_notes = "word count parse failed; treated as 0"
        issues.append("Word-count parse failed; treated as 0")
    dp_score = max(0.0, min(20.0, dp_score))
    breakdown["depth_wordcount"] = {
        "score": round(dp_score, 1), "max": 20.0, "notes": dp_notes,
    }

    # ---- 维度 4：internal_links（满分 20）----
    il_score = 0.0
    il_notes = []
    try:
        links = extract_links(html)
        # 站内兄弟页面的 URL 集合（来自 related）。
        sibling_urls = {_normalize_url(r.get("url", "")) for r in related if r.get("url")}
        sibling_urls.discard("")
        pillar_norm = _normalize_url(pillar_url) if pillar_url else ""
        self_norm = _normalize_url(page_url) if page_url else ""
        is_pillar = page_type == "pillar"

        href_norms = [_normalize_url(l["href"]) for l in links if l.get("href")]

        if is_pillar:
            # 主页：应链到全部兄弟页。
            if sibling_urls:
                linked = sibling_urls & set(href_norms)
                frac = len(linked) / float(len(sibling_urls))
                il_score += 16.0 * frac
                il_notes.append(f"links to {len(linked)}/{len(sibling_urls)} siblings")
                if frac < 1.0:
                    issues.append(
                        f"Pillar links to only {len(linked)}/{len(sibling_urls)} sibling pages "
                        f"(should link to all)")
            else:
                il_notes.append("no sibling set provided")
        else:
            # 簇页：恰好一次链到 pillar + 2-3 个兄弟链接。
            pillar_hits = href_norms.count(pillar_norm) if pillar_norm else 0
            if pillar_hits == 1:
                il_score += 8
            elif pillar_hits == 0:
                issues.append("Missing internal link up to pillar")
            else:
                il_score += 4
                issues.append(f"Links to pillar {pillar_hits} times (should be exactly once)")
            il_notes.append(f"pillar links={pillar_hits}")

            sib_links = [u for u in href_norms if u in sibling_urls and u != pillar_norm]
            n_sib = len(set(sib_links))
            if 2 <= n_sib <= 3:
                il_score += 8
            elif n_sib == 1:
                il_score += 4
                issues.append("Only 1 sibling link; aim for 2-3 relevant siblings")
            elif n_sib == 0:
                issues.append("No sibling internal links; add 2-3 to relevant cluster pages")
            else:  # >3
                il_score += 6
                issues.append(f"{n_sib} sibling links; cap cluster pages at 2-3 in-body siblings")
            il_notes.append(f"sibling links={n_sib}")

        # 被禁锚文本扣分（每个 -4，地板 0）。
        bad_anchor_penalty = 0
        for l in links:
            anchor = (l.get("anchor") or "").strip().lower()
            href = (l.get("href") or "").strip()
            is_bad = False
            if anchor in FORBIDDEN_ANCHORS:
                is_bad = True
            elif not anchor:
                is_bad = True
            elif re.match(r"(?i)^https?://", anchor):  # 锚文本就是裸 URL
                is_bad = True
            if is_bad:
                bad_anchor_penalty += 4
                issues.append(f"Non-descriptive/forbidden anchor text: '{l.get('anchor','')[:40]}'")
        il_score -= bad_anchor_penalty

        # 所有锚文本都描述性（>=2 词且非 URL）则 +4。
        if links:
            all_descriptive = all(
                len((l.get("anchor") or "").split()) >= 2
                and not re.match(r"(?i)^https?://", (l.get("anchor") or "").strip())
                for l in links
            )
            if all_descriptive:
                il_score += 4

        # 链到簇外 slug：提示问题，不给信用（不额外扣分，只警示）。
        known = set(sibling_urls)
        if pillar_norm:
            known.add(pillar_norm)
        if self_norm:
            known.add(self_norm)
        for l in links:
            hn = _normalize_url(l.get("href", ""))
            if hn and re.match(r"(?i)^https?://", l.get("href", "")) and hn not in known:
                # 仅对看起来像站内绝对链接的做提示（同源由 run 决定，这里宽松提示）
                pass
    except Exception:
        il_score = 0.0
        issues.append("Internal-link parse failed; treated as 0")
    il_score = max(0.0, min(20.0, il_score))
    breakdown["internal_links"] = {
        "score": round(il_score, 1), "max": 20.0, "notes": "; ".join(il_notes) or "ok",
    }

    # ---- 维度 5：specificity_antislop（满分 15）----
    sp_score = 0.0
    sp_notes = []
    try:
        low_body = body_text.lower()
        # 规格信号命中数。
        signal_hits = 0
        for pat in SPEC_SIGNAL_PATTERNS:
            if re.search(pat, low_body, re.IGNORECASE):
                signal_hits += 1
        if signal_hits >= 3:
            sp_score += 8
        else:
            issues.append(
                f"Only {signal_hits} spec signals (numbers+units/standards); add concrete data")
        sp_notes.append(f"spec signals={signal_hits}")

        # 反 slop 扣分（每个 -3，地板 0）。
        banned_found = []
        for phrase in BANNED_PHRASES:
            if phrase in low_body:
                banned_found.append(phrase)
        # 去重（弯/直引号变体只算一次概念，但逐字短语都罚）
        for phrase in set(banned_found):
            sp_score -= 3
            issues.append(f"Banned AI-slop phrase: '{phrase}'")
        sp_notes.append(f"banned phrases={len(set(banned_found))}")

        # 零 slop 且至少一个认证/标准 → +7。
        has_cert = any(tok in low_body for tok in CERT_STANDARD_TOKENS)
        if not banned_found and has_cert:
            sp_score += 7
        elif not has_cert:
            issues.append("No named cert/standard (ISO/ASTM/REACH/OEKO-TEX...) cited")
    except Exception:
        sp_score = 0.0
        issues.append("Specificity parse failed; treated as 0")
    sp_score = max(0.0, min(15.0, sp_score))
    breakdown["specificity_antislop"] = {
        "score": round(sp_score, 1), "max": 15.0, "notes": "; ".join(sp_notes) or "ok",
    }

    # ---- 维度 6：meta_title_quality（满分 10）----
    mt_score = 0.0
    mt_notes = []
    try:
        tlen = len(title)
        mlen = len(meta)
        # 标题 50-60 满分 +4；40-65 部分。
        if 50 <= tlen <= 60:
            mt_score += 4
        elif 40 <= tlen <= 65:
            mt_score += 2
            issues.append(f"Title {tlen} chars (target 50-60)")
        else:
            issues.append(f"Title {tlen} chars (target 50-60)")
        # meta 140-160 满分 +4；120-170 部分。
        if 140 <= mlen <= 160:
            mt_score += 4
        elif 120 <= mlen <= 170:
            mt_score += 2
            issues.append(f"Meta description {mlen} chars (target 140-160)")
        else:
            issues.append(f"Meta description {mlen} chars (target 140-160)")
        # meta 不等于 title、且不是 title 的前缀。
        t_norm = title.strip().lower()
        m_norm = meta.strip().lower()
        if m_norm and m_norm != t_norm and not t_norm.startswith(m_norm):
            mt_score += 2
        else:
            issues.append("Meta description duplicates or is a prefix of the title")
        mt_notes.append(f"title={tlen}c, meta={mlen}c")
    except Exception:
        mt_score = 0.0
        issues.append("Meta/title parse failed; treated as 0")
    mt_score = max(0.0, min(10.0, mt_score))
    breakdown["meta_title_quality"] = {
        "score": round(mt_score, 1), "max": 10.0, "notes": "; ".join(mt_notes) or "ok",
    }

    # ---- 汇总 ----
    total = sum(d["score"] for d in breakdown.values())
    total = round(max(0.0, min(100.0, total)), 1)

    return {
        "score": total,
        "breakdown": breakdown,
        "issues": issues,
        "passed": total >= PASS_THRESHOLD,
    }
