# -*- coding: utf-8 -*-
"""lib/quality_ext.py · Phase 4: 扩展质量检查

不修改 lib/quality.py。新增维度: readability, duplicate, sanitize。
"""

import re


def sanitize_html(html: str) -> str:
    """移除危险 HTML 标签/属性。

    移除: script, iframe, onerror, onclick, javascript:, onload
    """
    if not html:
        return ""

    # 移除标签
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<iframe\b[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 移除危险属性
    dangerous_attrs = [
        r'\bonerror\s*=\s*"[^"]*"',
        r"\bonerror\s*=\s*'[^']*'",
        r'\bonclick\s*=\s*"[^"]*"',
        r"\bonclick\s*=\s*'[^']*'",
        r'\bonload\s*=\s*"[^"]*"',
        r"\bonload\s*=\s*'[^']*'",
        r'\bonfocus\s*=\s*"[^"]*"',
        r"\bonfocus\s*=\s*'[^']*'",
        r'\bjavascript\s*:',  # javascript: URLs
    ]
    for pat in dangerous_attrs:
        html = re.sub(pat, '', html, flags=re.IGNORECASE)

    return html


def readability_score(text_or_html: str) -> dict:
    """可读性评分 (简化 Python 实现)。

    Returns:
        {"flesch_approx": float, "grade_level": float, "word_count": int,
         "sentence_count": int, "ok": bool}
    """
    # 去 HTML
    text = re.sub(r'<[^>]+>', '', text_or_html or '')
    if not text.strip():
        return {"flesch_approx": 0, "grade_level": 0, "word_count": 0,
                "sentence_count": 0, "ok": False}

    # 统计
    words = [w for w in re.findall(r'[a-zA-Z]+', text)]
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    sentence_count = len(sentences) if sentences else 1
    syllable_count = sum(_count_syllables(w) for w in words)

    # Flesch Reading Ease (简化版)
    if word_count > 0 and sentence_count > 0:
        flesch = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
    else:
        flesch = 0

    # Flesch-Kincaid Grade Level
    if word_count > 0 and sentence_count > 0:
        grade = 0.39 * (word_count / sentence_count) + 11.8 * (syllable_count / word_count) - 15.59
    else:
        grade = 0

    # B2B 内容: flesch 30-60 是合理的, <20 太复杂
    ok = word_count > 300 and flesch > 10

    return {
        "flesch_approx": round(flesch, 1),
        "grade_level": round(grade, 1),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "ok": ok,
    }


def _count_syllables(word: str) -> int:
    """简化音节计数。"""
    word = word.lower().strip()
    if len(word) <= 3:
        return 1
    syllables = len(re.findall(r'[aeiouy]+', word))
    return max(1, syllables)


def duplicate_similarity(page_a, page_b) -> float:
    """跨页重复检测 (Jaccard 相似度)。

    Returns:
        0.0-1.0, 越高越重复
    """
    def _words(content):
        if hasattr(content, 'body_html'):
            text = content.body_html
        elif isinstance(content, dict):
            text = content.get('body_html', '') or content.get('title', '')
        else:
            text = str(content)
        text = re.sub(r'<[^>]+>', '', text).lower()
        return set(re.findall(r'[a-z]{4,}', text))

    wa = _words(page_a)
    wb = _words(page_b)
    if not wa or not wb:
        return 0.0

    intersection = wa & wb
    union = wa | wb
    return len(intersection) / len(union) if union else 0.0


def extended_quality_check(page_content, sibling_pages=None) -> dict:
    """扩展质量检查。

    Returns:
        {"ok": bool, "readability": {...}, "duplicate_risk": float,
         "html_safe": bool, "issues": [...]}
    """
    html = ""
    if hasattr(page_content, 'body_html'):
        html = page_content.body_html
    elif isinstance(page_content, dict):
        html = page_content.get('body_html', '')

    issues = []

    # 1. readability
    read = readability_score(html)
    if not read["ok"]:
        issues.append(f"Readability low: {read.get('flesch_approx', 0)} {read.get('word_count', 0)} words")

    # 2. sanitize
    safe_html = sanitize_html(html)
    html_safe = (safe_html == html or len(safe_html) >= len(html) * 0.95)
    if not html_safe:
        issues.append("HTML contains dangerous elements (script/iframe/onclick)")

    # 3. duplicate
    dup_risk = 0.0
    if sibling_pages:
        for sib in sibling_pages:
            sim = duplicate_similarity(page_content, sib)
            dup_risk = max(dup_risk, sim)
        if dup_risk > 0.7:
            issues.append(f"High duplicate risk: {dup_risk:.2f}")

    ok = len(issues) == 0 or (html_safe and dup_risk < 0.9)

    return {
        "ok": ok,
        "readability": read,
        "duplicate_risk": round(dup_risk, 3),
        "html_safe": html_safe,
        "issues": issues,
    }
