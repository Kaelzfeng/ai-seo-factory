# -*- coding: utf-8 -*-
"""lib/gutenberg_emitter.py · Phase 4: HTML → WordPress Gutenberg 块

纯字符串转换, 不引入 GPL 依赖。
"""

import re


def html_to_gutenberg_blocks(html: str) -> str:
    """把 HTML 字符串转为 Gutenberg 块 HTML。

    支持: h1-h3, p, ul, ol, blockquote, table
    不支持的标签用 <!-- wp:html --> 包裹。
    """
    if not html or not html.strip():
        return ""

    # 逐元素处理
    result = []
    # 用正则拆分顶层元素
    # 简化: 按 block-level 标签拆分
    pattern = re.compile(
        r'(<(?:h[1-3]|p|ul|ol|blockquote|table)\b[^>]*>.*?</(?:h[1-3]|p|ul|ol|blockquote|table)>)',
        re.DOTALL | re.IGNORECASE
    )

    parts = pattern.split(html)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        tag_match = re.match(r'<(\w+)', part, re.IGNORECASE)
        if not tag_match:
            # 非标签文本 → paragraph wrap
            if part:
                result.append(f'<!-- wp:paragraph -->\n<p>{part}</p>\n<!-- /wp:paragraph -->')
            continue

        tag = tag_match.group(1).lower()

        if tag in ('h1', 'h2', 'h3'):
            level = tag[1]
            cleaned = re.sub(r'</?h\d[^>]*>', '', part, flags=re.IGNORECASE).strip()
            result.append(f'<!-- wp:heading {{"level":{level}}} -->\n<h{level}>{cleaned}</h{level}>\n<!-- /wp:heading -->')
        elif tag == 'p':
            cleaned = part.strip()
            result.append(f'<!-- wp:paragraph -->\n{cleaned}\n<!-- /wp:paragraph -->')
        elif tag in ('ul', 'ol'):
            result.append(f'<!-- wp:list -->\n{part.strip()}\n<!-- /wp:list -->')
        elif tag == 'blockquote':
            result.append(f'<!-- wp:quote -->\n{part.strip()}\n<!-- /wp:quote -->')
        elif tag == 'table':
            result.append(f'<!-- wp:table -->\n{part.strip()}\n<!-- /wp:table -->')
        else:
            result.append(f'<!-- wp:html -->\n{part.strip()}\n<!-- /wp:html -->')

    return '\n'.join(result)


def page_content_to_gutenberg(page_content) -> str:
    """把 PageContent 转为完整 Gutenberg 输出。

    Returns Gutenberg HTML 字符串。
    """
    if hasattr(page_content, 'body_html'):
        html = page_content.body_html
    elif isinstance(page_content, dict):
        html = page_content.get('body_html', '')
    else:
        html = str(page_content)

    return html_to_gutenberg_blocks(html)


def strip_gutenberg_comments(html: str) -> str:
    """移除 Gutenberg 注释, 保留可读 HTML。"""
    # 移除 <!-- wp:... --> 和 <!-- /wp:... --> 注释
    cleaned = re.sub(r'<!--\s*/?wp:[^>]*-->', '', html)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()
