# -*- coding: utf-8 -*-
"""run.py · 内容生成管线 + SEO 润色循环

串联: intake → keyword_scout → llm → quality → polish → schema → preview / wp_publish

Phase 1.1: 4-tier 分层 LLM 重试 + partial_success + retry_pending 失败页可恢复。
"""

import datetime
import json
import os
import sys
import time
import traceback
from pathlib import Path

import yaml

from lib import llm as _llm_mod
from lib import quality as _quality_mod
from lib import preview, schema

# 模块级别名，测试可 monkeypatch 覆写
llm = _llm_mod
quality = _quality_mod

ROOT = Path(__file__).resolve().parent

# LLM 重试配置 (Phase 1.1: 4-tier progressive)
_RETRY_DELAY_SEC = 1.5
_MAX_TOTAL_ATTEMPTS = 4   # 总共 4 次: normal, retry, strict, fallback


# ── 工具 ────────────────────────────────────────────


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _today_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _content_is_valid(content, required_keys=("title", "meta_description", "html")) -> tuple[bool, str]:
    """验证 LLM 返回的 content dict 是否有效。

    Returns:
        (is_valid, reason) — is_valid=True 表示至少 required_keys 都有非空字符串值。
    """
    if content is None:
        return False, "LLM 返回 None"
    if not isinstance(content, dict):
        return False, f"LLM 返回非 dict 类型: {type(content).__name__}"
    if len(content) == 0:
        return False, "LLM 返回空 dict {}"
    for key in required_keys:
        if key not in content:
            return False, f"缺少必需字段 '{key}'"
        val = content.get(key)
        if not val or not isinstance(val, str) or not val.strip():
            return False, f"字段 '{key}' 为空或非字符串"
    return True, "ok"


def _content_is_valid_detailed(content, required_keys=("title", "meta_description", "html")) -> dict:
    """详细诊断 LLM 返回内容,返回结构化信息供日志使用。

    Returns:
        {"valid": bool, "reason": str, "response_type": str, "missing_fields": [...]}
    """
    if content is None:
        return {"valid": False, "reason": "LLM 返回 None",
                "response_type": "None", "missing_fields": list(required_keys)}
    if not isinstance(content, dict):
        return {"valid": False, "reason": f"LLM 返回非 dict 类型: {type(content).__name__}",
                "response_type": type(content).__name__, "missing_fields": list(required_keys)}
    if len(content) == 0:
        return {"valid": False, "reason": "LLM 返回空 dict {}",
                "response_type": "empty_dict", "missing_fields": list(required_keys)}

    missing = []
    for key in required_keys:
        if key not in content:
            missing.append(key)
        else:
            val = content.get(key)
            if not val or not isinstance(val, str) or not val.strip():
                missing.append(key)

    if missing:
        return {"valid": False, "reason": f"缺少/空字段: {missing}",
                "response_type": "dict_missing_fields", "missing_fields": missing}

    return {"valid": True, "reason": "ok",
            "response_type": "dict_valid", "missing_fields": []}


def _build_fallback_prompt(user_prompt: str, page_type: str, target_kw: str) -> str:
    """构建极简回退 prompt: 只要求输出最小必需字段。"""
    return f"""You MUST return a valid JSON object with exactly these three fields:
- "title": a B2B SEO page title about {target_kw}
- "meta_description": a 150-160 character meta description about {target_kw}
- "html": well-structured HTML content with h2/h3 headings about {target_kw}

Page type: {page_type}

Output ONLY the JSON object. No markdown, no code fences, no extra text.
Example: {{"title": "...", "meta_description": "...", "html": "..."}}"""


def _build_strict_reminder(user_prompt: str) -> str:
    """在 prompt 末尾追加严格 JSON 提醒。"""
    return user_prompt + """

CRITICAL INSTRUCTION: You MUST return a valid JSON object with ALL of these fields:
"title", "meta_description", "html". Each field MUST contain a non-empty string.
Do NOT return an empty object {{}}. Return ONLY valid JSON — no markdown, no code fences."""


def _call_llm_with_retry(system_prompt: str, user_prompt: str,
                         schema_def: dict, page_label: str,
                         page_type: str = "guide", page_slug: str = "",
                         target_kw: str = "") -> dict:
    """Phase 1.1: 4-tier 分层 LLM 重试。

    attempt 1: 正常 prompt
    attempt 2: 原 prompt 重试
    attempt 3: 追加 strict JSON reminder
    attempt 4: fallback minimal schema prompt

    每次失败记录详细诊断: attempt, reason, response_type, missing_fields, page_slug, page_type

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        schema_def: JSON Schema 定义
        page_label: 日志用页面标识
        page_type: 页面类型
        page_slug: 页面 slug
        target_kw: 目标关键词

    Returns:
        content dict(on success)

    Raises:
        RuntimeError: 4 次全部失败,携带最后一轮的诊断信息
    """
    strategies = [
        # (label, system_modifier, user_modifier)
        ("normal", None, None),
        ("retry", None, None),
        ("strict_json", None, _build_strict_reminder),
        ("fallback_minimal", "fallback", _build_fallback_prompt),
    ]
    # 限制实际尝试次数
    active_strategies = strategies[:_MAX_TOTAL_ATTEMPTS]

    last_diagnostic = None

    for attempt_idx, (strategy_label, sys_mod, user_mod) in enumerate(active_strategies):
        # 构建本次尝试的 prompt
        if strategy_label == "fallback_minimal":
            # 极简模式: 短 system + 只要求必需字段的 user
            cur_system = "You are a B2B SEO content writer. Return valid JSON with title, meta_description, and html fields only."
            cur_user = _build_fallback_prompt(user_prompt, page_type, target_kw)
        elif strategy_label == "strict_json":
            cur_system = system_prompt
            cur_user = user_mod(user_prompt) if user_mod else user_prompt
        else:
            cur_system = system_prompt
            cur_user = user_prompt

        # 调用 LLM
        try:
            content = llm.structured(
                model=llm.default_model("writer"),
                system=cur_system,
                user=cur_user,
                schema=schema_def,
            )
        except Exception as e:
            last_diagnostic = {
                "attempt": attempt_idx + 1,
                "strategy": strategy_label,
                "reason": f"LLM 调用异常: {e}",
                "response_type": "exception",
                "missing_fields": list(schema_def.get("required", [])),
                "page_slug": page_slug,
                "page_type": page_type,
            }
            if attempt_idx < _MAX_TOTAL_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_SEC)
            continue

        # 验证内容
        diag = _content_is_valid_detailed(content, tuple(schema_def.get("required", [])))
        if diag["valid"]:
            return content

        # 记录失败诊断
        last_diagnostic = {
            "attempt": attempt_idx + 1,
            "strategy": strategy_label,
            "reason": diag["reason"],
            "response_type": diag["response_type"],
            "missing_fields": diag["missing_fields"],
            "page_slug": page_slug,
            "page_type": page_type,
        }

        if attempt_idx < _MAX_TOTAL_ATTEMPTS - 1:
            time.sleep(_RETRY_DELAY_SEC)

    # 全部失败: 构造详细错误信息
    detail = json.dumps(last_diagnostic or {}, ensure_ascii=False)
    raise RuntimeError(f"LLM 4 次尝试全部失败 | last: {detail}")


# ── SEO Polish ──────────────────────────────────────


def polish_page(page: dict,
                orig_content: dict,
                q_orig: dict,
                industry: dict,
                profile: str = "seo-content-polish",
                on_delta=None) -> tuple[dict, dict]:
    """对单页内容做一轮 LLM 润色,保留更好的版本。

    Args:
        page: 页面元信息 {slug, target_keyword, title, type, ...}
        orig_content: 原始内容 {title, meta_description, html, image_query}
        q_orig: 原始质量评分 {score, issues, ...}
        industry: 行业配置 dict
        profile: skill 名称,默认 seo-content-polish
        on_delta: 流式回调(text) 或 None

    Returns:
        (content_dict, quality_dict)
        如果润色版评分更高,返回润色版;否则返回原版。
        如果 LLM 调用失败,返回原版(不抛异常)。
    """
    issues = q_orig.get("issues", [])
    if not issues:
        return orig_content, q_orig

    try:
        polish_skill = llm.load_skill(profile)
    except Exception:
        polish_skill = ""

    page_type = page.get("type", "guide")
    target_kw = page.get("target_keyword", "")
    issue_list = "\n".join(f"- {i}" for i in issues)

    user_prompt = f"""Polish this {page_type} page targeting "{target_kw}".

Current quality score: {q_orig.get('score', 0)}/100

Issues to fix:
{issue_list}

Title: {orig_content.get('title', '')}
Meta description: {orig_content.get('meta_description', '')}

HTML content:
{orig_content.get('html', '')}

Return the polished version with the same structure (title, meta_description, html, image_query)."""

    schema_def = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "meta_description": {"type": "string"},
            "html": {"type": "string"},
            "image_query": {"type": "string"},
        },
        "required": ["title", "meta_description", "html"],
    }

    try:
        polished = llm.structured(
            model=llm.default_model("polish"),
            system=polish_skill,
            user=user_prompt,
            schema=schema_def,
        )
    except Exception:
        return orig_content, q_orig

    valid, _ = _content_is_valid(polished)
    if not valid:
        return orig_content, q_orig

    try:
        q_polished = quality.score_page(page, polished, industry)
    except Exception:
        q_polished = {"score": 0, "issues": ["评分失败"]}

    if q_polished.get("score", 0) >= q_orig.get("score", 0):
        return polished, q_polished
    else:
        return orig_content, q_orig


# ── 内部步骤函数 ─────────────────────────────────────


def _prepare_generation(project: dict, bypass_subscription: bool = False) -> dict:
    """准备生成:订阅检查 + 读取行业配置 + 关键词规划。

    Returns:
        {"ok": True/False, "industry": {...}, "pages": [...], "errors": [...], "subscription_check": {...}}
        如果 ok=False,调用方应直接返回错误结果。
    """
    prep = {"ok": False, "industry": {}, "pages": [], "errors": [], "subscription_check": {}}
    tenant_id = project.get("tenant_id")

    # 1. SaaS 额度检查
    if tenant_id and not bypass_subscription:
        from lib.subscription import check_generation_allowed
        check = check_generation_allowed(tenant_id)
        prep["subscription_check"] = check
        if not check.get("allowed"):
            prep["errors"].append(f"额度检查失败: {check.get('reason')}")
            return prep
    elif bypass_subscription:
        prep["subscription_check"] = {"bypassed": True}

    # 2. 读取行业配置
    industry_config_path = project.get("industry_config", "")
    if industry_config_path and Path(industry_config_path).exists():
        industry = _load_yaml(industry_config_path)
    else:
        industry = {"name": project.get("name", "Untitled"),
                    "seed_keyword": project.get("seed_keyword", ""),
                    "language": project.get("language", "English")}
    prep["industry"] = industry

    # 3. 关键词规划
    pages = list(industry.get("pages", []))
    if not pages:
        seed = industry.get("seed_keyword", project.get("seed_keyword", ""))
        try:
            from lib.keyword_scout import grounded_plan
            gp = grounded_plan(seed, max_pages=7)
            pages = list(gp.get("plan", []))
        except Exception as e:
            prep["errors"].append(f"关键词规划失败: {e}")
            pages = []

    if not pages:
        prep["errors"].append("未生成任何页面计划。")
        return prep

    prep["pages"] = pages
    prep["ok"] = True
    return prep


def _generate_page_content(page_plan: dict, industry: dict, seed: str,
                           org_name: str, today: str, page_index: int,
                           total_pages: int) -> dict:
    """为单个页面生成内容(LLM + 4-tier 重试)。

    Returns:
        {"content": {...}, "page": {...}}  on success

    Raises:
        RuntimeError: LLM 4 次全部失败(带详细诊断)
    """
    page = dict(page_plan)
    page_type = page.get("type", "guide")
    target_kw = page.get("target_keyword", seed)
    page_slug = page.get("slug", f"page-{page_index}")
    page_label = f"第 {page_index}/{total_pages} 页 [{page_type}] {target_kw}"

    skill_name = "seo-content"
    system_prompt = llm.load_skill(skill_name)

    user_prompt = f"""Write a {page_type} page for a B2B industrial website.

INDUSTRY: {industry.get('name', '')}
SEED KEYWORD: {seed}
TARGET KEYWORD: {target_kw}
PAGE TITLE: {page.get('title', target_kw)}
PAGE TYPE: {page_type}
LANGUAGE: {industry.get('language', 'English')}
TONE: {industry.get('tone', 'Professional, factual')}
CURRENT DATE: {today}
ORGANIZATION: {org_name}

Create the page with title, meta_description (150-160 chars), html (well-structured with h2/h3 headings), and an image_query for a relevant photo."""

    schema_def = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "meta_description": {"type": "string"},
            "html": {"type": "string"},
            "image_query": {"type": "string"},
        },
        "required": ["title", "meta_description", "html"],
    }

    content = _call_llm_with_retry(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_def=schema_def,
        page_label=page_label,
        page_type=page_type,
        page_slug=page_slug,
        target_kw=target_kw,
    )

    return {"content": content, "page": page}


def _score_page(page: dict, content: dict, industry: dict) -> dict:
    """对页面内容做质量评分。"""
    return quality.score_page(page, content, industry)


def _polish_if_needed(page: dict, content: dict, q_result: dict,
                      industry: dict) -> tuple:
    """如果质量未通过,执行润色;否则返回原版。"""
    if not q_result.get("passed", False):
        return polish_page(page, content, q_result, industry,
                          profile="seo-content-polish")
    return content, q_result


def _attach_schema(content: dict) -> dict:
    """为内容附加 schema.org JSON-LD(占位,后续扩展)。"""
    # schema 注入已在 preview.render_html 中处理,此处为显式步骤占位
    return content


def _write_preview(all_pages: list, site_url: str, output_dir=None) -> list:
    """渲染 HTML 预览文件到 output_src/。

    Returns:
        errors list
    """
    errors = []
    if not all_pages:
        return errors

    outdir = Path(output_dir) if output_dir else ROOT / "output_src"
    outdir.mkdir(parents=True, exist_ok=True)

    for entry in all_pages:
        page = entry["page"]
        content = entry["content"]
        try:
            html = preview.render_html(
                page, content,
                site=site_url,
                all_pages=[e["page"] for e in all_pages],
            )
            slug = page.get("slug", f"page-{all_pages.index(entry)}")
            out_path = outdir / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            entry["output_path"] = str(out_path)
            entry["html"] = html
        except Exception as e:
            errors.append(f"渲染 {page.get('slug')} 失败: {e}")

    # 写 index
    try:
        preview.write_index(
            [e["page"] for e in all_pages],
            str(outdir),
        )
    except Exception as e:
        errors.append(f"写 index 失败: {e}")

    return errors


def _publish_if_needed(mode: str, project: dict, all_pages: list,
                       tenant_id: int = None) -> list:
    """发布到 WordPress(仅 publish 模式)。

    Returns:
        errors list
    """
    errors = []
    if mode != "publish":
        return errors

    wp_url = project.get("wp_url", "")
    wp_user = project.get("wp_username", "")
    wp_pass = project.get("wp_app_password", "")
    if not (wp_url and wp_user and wp_pass):
        errors.append("缺少 WordPress 凭据,跳过发布。")
        return errors

    project_id = project.get("id", 0)

    try:
        from lib.wp_publish import WordPress
        wp = WordPress(site=wp_url, user=wp_user, app_password=wp_pass)

        for entry in all_pages:
            page = entry["page"]
            content = entry["content"]
            slug = page.get("slug", "")
            gen_id = page.get("gen_id")

            try:
                pub_result = wp.create_post(
                    title=content.get("title", page.get("title", "")),
                    html=entry.get("html", content.get("html", "")),
                    slug=slug,
                    meta_description=content.get("meta_description", ""),
                )
                remote_id = str(pub_result.get("id", ""))
                remote_url = str(pub_result.get("link", ""))

                # 记录 CMS 发布成功
                try:
                    from lib.cms_logs import record_publish_success
                    record_publish_success(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        generation_id=gen_id,
                        remote_id=remote_id,
                        remote_url=remote_url,
                        meta={"slug": slug},
                    )
                except Exception:
                    pass

            except Exception as e:
                err_str = str(e)
                errors.append(f"发布 {slug} 失败: {err_str}")

                # 记录 CMS 发布失败
                try:
                    from lib.cms_logs import record_publish_failure
                    record_publish_failure(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        generation_id=gen_id,
                        error=err_str,
                        meta={"slug": slug},
                    )
                except Exception:
                    pass

    except Exception as e:
        errors.append(f"WordPress 初始化失败: {e}")

    return errors


def _record_generation(tenant_id: int, project: dict, all_pages: list,
                       bypass_subscription: bool = False) -> dict:
    """记录用量(仅当有 tenant 且未 bypass 时)。

    Returns:
        usage dict 或 {}
    """
    if not tenant_id or bypass_subscription:
        return {}

    usage_info = {}
    try:
        from models import record_usage
        usage = llm.last_usage()
        token_count = usage.get("total_tokens", 0)
        page_count = len(all_pages)
        if page_count > 0:
            record_usage(tenant_id, user_id=project.get("user_id"),
                        project_id=project.get("id", 0), kind="generation",
                        amount=page_count)
        if token_count > 0:
            record_usage(tenant_id, user_id=project.get("user_id"),
                        project_id=project.get("id", 0), kind="token",
                        amount=token_count)
        usage_info = {"pages": page_count, "tokens": token_count}
    except Exception:
        pass
    return usage_info


# ── 生成站点 ────────────────────────────────────────


def generate_site(project: dict, mode: str = "dry-run",
                  bypass_subscription: bool = False,
                  output_dir=None,
                  progress_callback=None) -> dict:
    """对单个 project 执行完整生成管线。

    Args:
        project: 项目字典,至少含 id, name, industry_config, seed_keyword, tenant_id 等
        mode: "dry-run"(本地输出) 或 "publish"(发布到 WordPress)
        bypass_subscription: True 时跳过 SaaS 额度检查(CLI dry-run 用)

    Returns:
        Unified structure:
        {"ok": True/False,
         "generation_id": ...,  "generation_ids": [...],
         "project_id": ..., "pages_total": ..., "pages_success": ..., "pages_failed": ...,
         "mode": ..., "usage": {...},
         "pages": [...], "errors": [...], "summary": {...}}
    """
    tenant_id = project.get("tenant_id")
    project_id = project.get("id", 0)

    # ── 1. 准备 ──
    prep = _prepare_generation(project, bypass_subscription=bypass_subscription)
    if not prep["ok"]:
        result = {
            "ok": False,
            "code": "generation_failed",
            "message": "; ".join(prep["errors"]),
            "generation_id": None,
            "generation_ids": [],
            "project_id": project_id,
            "pages_total": 0,
            "pages_success": 0,
            "pages_failed": 0,
            "mode": mode,
            "usage": {},
            "pages": [],
            "errors": prep["errors"],
            "summary": {"subscription_check": prep["subscription_check"]},
        }
        return result

    industry = prep["industry"]
    pages = prep["pages"]
    subscription_check = prep["subscription_check"]

    seed = industry.get("seed_keyword", project.get("seed_keyword", ""))
    org_name = industry.get("org_name", project.get("name", "Demo Co."))
    site_url = project.get("site_url", "") or industry.get("site_url", "https://example.com")

    # ── 2. 注入当前日期 ──
    today = _today_str()
    os.environ["CURRENT_DATE"] = today

    # ── 3. 逐页生成 ──
    all_pages = []
    generation_ids = []       # 成功页的 generation ID
    failed_gen_ids = []        # 失败页的 generation ID (供补跑用)
    page_errors = []
    total_pages = len(pages)

    if progress_callback:
        progress_callback("stage", {"stage": "generating", "label": "逐页生成",
            "message": f"共 {total_pages} 页, 开始生成…"})
        progress_callback("progress", {"current": 0, "total": total_pages,
            "percent": 0, "elapsed": 0})

    for i, page_plan in enumerate(pages):
        page_entry = None
        gen_id = None
        page_type = page_plan.get("type", "guide")
        target_kw = page_plan.get("target_keyword", seed)
        page_slug = page_plan.get("slug", f"page-{i+1}")
        page_label = f"第 {i+1}/{total_pages} 页 [{page_type}] {target_kw}"

        try:
            # ── page_start event ──
            if progress_callback:
                progress_callback("page_start", {
                    "slug": page_slug,
                    "title": page_plan.get("title", target_kw),
                    "index": i + 1,
                    "total": total_pages,
                    "status": "generating",
                })

            # 3a. LLM 生成
            gen_result = _generate_page_content(
                page_plan, industry, seed, org_name, today,
                page_index=i + 1, total_pages=total_pages,
            )
            content = gen_result["content"]
            page = gen_result["page"]

            # ── page_preview event ──
            if progress_callback:
                progress_callback("page_preview", {
                    "slug": page_slug,
                    "title": content.get("title", ""),
                    "html": content.get("html", ""),
                    "status": "preview",
                })

            # 3b. 记录到 generations 表 + generation_logs
            try:
                from models import create_generation
                gen_id = create_generation(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    status="running",
                    keyword=target_kw,
                    page_type=page_type,
                    title=content.get("title", ""),
                    slug=page.get("slug", page_slug),
                    page_count=1,
                    passed_count=0,
                )
                page["gen_id"] = gen_id
                from lib.generation_logs import log_generation_step
                log_generation_step(
                    tenant_id=tenant_id, project_id=project_id,
                    generation_id=gen_id, step="llm_generate",
                    status="success", message="LLM 生成完成",
                    meta={"page_type": page_type, "keyword": target_kw, "strategy": "normal_to_fallback"},
                )
            except Exception:
                pass

            # 3c. 质量评分
            q_result = _score_page(page, content, industry)

            # ── log score event ──
            if progress_callback:
                progress_callback("log", {
                    "level": "info" if q_result.get("passed") else "warning",
                    "message": f"{page_slug}: 得分 {q_result.get('score', 0):.0f}/100 {'PASS' if q_result.get('passed') else 'NEEDS_POLISH'}",
                    "time": time.strftime("%H:%M:%S"),
                })

            try:
                if gen_id:
                    from lib.generation_logs import log_generation_step
                    log_generation_step(
                        tenant_id=tenant_id, project_id=project_id,
                        generation_id=gen_id, step="quality_score",
                        status="success" if q_result.get("passed") else "running",
                        message=f"Score: {q_result.get('score', 0):.0f}/100",
                        meta={"score": q_result.get("score"), "passed": q_result.get("passed")},
                    )
            except Exception:
                pass

            # 3d. 润色(如未通过)
            content, q_result = _polish_if_needed(page, content, q_result, industry)
            try:
                if gen_id:
                    from lib.generation_logs import log_generation_step
                    step_status = "success" if q_result.get("passed") else "running"
                    log_generation_step(
                        tenant_id=tenant_id, project_id=project_id,
                        generation_id=gen_id, step="polish",
                        status=step_status,
                        message=f"Post-polish score: {q_result.get('score', 0):.0f}/100",
                        meta={"score": q_result.get("score"), "passed": q_result.get("passed")},
                    )
            except Exception:
                pass

            # 3e. 附加 schema
            content = _attach_schema(content)

            # 更新 generation 记录为完成/草稿
            try:
                if gen_id:
                    from models import update_generation
                    final_status = "completed" if q_result.get("passed", False) else "draft"
                    update_generation(gen_id, status=final_status,
                                     quality_score=q_result.get("score", 0.0),
                                     passed_count=1 if q_result.get("passed") else 0)
            except Exception:
                pass

            generation_ids.append(gen_id)
            all_pages.append({
                "page": page,
                "content": content,
                "quality": q_result,
            })

            # ── page_done event ──
            if progress_callback:
                progress_callback("page_done", {
                    "slug": page_slug,
                    "title": content.get("title", ""),
                    "url": f"./{page_slug}.html",
                    "score": q_result.get("score", 0),
                    "passed": q_result.get("passed", False),
                    "status": "done",
                })
                done_count = i + 1
                progress_callback("progress", {
                    "current": done_count,
                    "total": total_pages,
                    "percent": int(done_count / total_pages * 100) if total_pages > 0 else 0,
                })

        except Exception as e:
            # Phase 1.1: 解析 LLM 失败诊断
            err_str = str(e)
            page_errors.append(f"{page_label} 生成失败: {err_str}")

            if progress_callback:
                progress_callback("log", {
                    "level": "error",
                    "message": f"{page_slug}: 生成失败 — {err_str}",
                    "time": time.strftime("%H:%M:%S"),
                })
                progress_callback("page_done", {
                    "slug": page_slug,
                    "title": page_plan.get("title", page_slug),
                    "status": "failed",
                    "error": err_str[:200],
                })

            # 记录失败 generation(状态 = retry_pending,供补跑)
            try:
                from models import create_generation
                gen_id = create_generation(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    status="retry_pending",
                    keyword=target_kw,
                    page_type=page_type,
                    title=page_plan.get("title", ""),
                    slug=page_slug,
                    page_count=0,
                    passed_count=0,
                )
                failed_gen_ids.append(gen_id)
            except Exception:
                pass

            # 记录详细失败诊断到 generation_logs
            try:
                from lib.generation_logs import log_generation_step
                # 从异常信息中提取 last diagnostic (JSON 部分)
                diag_meta = {"page_index": i + 1, "slug": page_slug,
                            "keyword": target_kw, "page_type": page_type,
                            "status": "retry_pending"}
                # 尝试提取 RuntimeError 中的 JSON diagnostic
                if "last:" in err_str:
                    try:
                        json_part = err_str.split("last:", 1)[1].strip()
                        extra = json.loads(json_part)
                        diag_meta.update(extra)
                    except (ValueError, json.JSONDecodeError):
                        pass
                log_generation_step(
                    tenant_id=tenant_id, project_id=project_id,
                    generation_id=gen_id, step="llm_generate",
                    status="failed", message=err_str[:500],
                    meta=diag_meta,
                )
            except Exception:
                pass
            continue

    # ── 4. 本地预览渲染 ──
    preview_errors = _write_preview(all_pages, site_url, output_dir=output_dir)

    # ── 5. 发布到 WordPress ──
    publish_errors = _publish_if_needed(mode, project, all_pages, tenant_id)

    # ── 6. 记录用量(Phase 1.1: 仅成功页计 generation usage, token 仍记录) ──
    usage_info = _record_generation(tenant_id, project, all_pages, bypass_subscription)

    # ── 7. 构建统一返回结构(Phase 1.1: partial_success + retryable) ──
    pages_total = total_pages
    pages_success = len(all_pages)
    pages_failed = pages_total - pages_success

    all_errors = page_errors + preview_errors + publish_errors

    # ── 逐页成功时写 generation_logs success ──
    for entry in all_pages:
        gen_id = entry["page"].get("gen_id")
        if gen_id:
            try:
                from lib.generation_logs import mark_generation_success
                mark_generation_success(gen_id)
            except Exception:
                pass

    # Phase 1.1: 确定结果码和 retryable
    if pages_success == pages_total:
        code = "success"
        ok = True
        retryable = False
    elif pages_success > 0:
        code = "partial_success"
        ok = False
        retryable = True
    else:
        code = "generation_failed"
        ok = False
        retryable = len(failed_gen_ids) > 0

    result = {
        "ok": ok,
        "code": code,
        "message": f"{pages_success}/{pages_total} pages generated successfully" if pages_success > 0 else "Generation failed",
        "retryable": retryable,
        "generation_id": generation_ids[0] if generation_ids else None,
        "generation_ids": generation_ids,
        "failed_generation_ids": failed_gen_ids,
        "project_id": project_id,
        "pages_total": pages_total,
        "pages_success": pages_success,
        "pages_failed": pages_failed,
        "mode": mode,
        "usage": usage_info,
        "pages": all_pages,
        "errors": all_errors,
        "summary": {
            "subscription_check": subscription_check,
            "total_pages": pages_success,
            "errors": len(all_errors),
        },
    }
    if usage_info:
        result["summary"]["usage_recorded"] = usage_info

    return result


# ── CLI 入口 ────────────────────────────────────────


def main():
    """python run.py <industry.yaml> [--dry-run|--publish]"""
    if len(sys.argv) < 2:
        print("Usage: python run.py <industry.yaml> [--dry-run|--publish]")
        sys.exit(1)

    config_path = sys.argv[1]
    mode = "dry-run"
    if "--publish" in sys.argv:
        mode = "publish"

    if not Path(config_path).exists():
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    industry = _load_yaml(config_path)

    # 构造伪 project dict(CLI 使用,无 tenant 且 bypass subscription)
    project = {
        "id": 0,
        "tenant_id": None,
        "user_id": None,
        "name": industry.get("name", "CLI Run"),
        "industry_config": config_path,
        "seed_keyword": industry.get("seed_keyword", ""),
        "language": industry.get("language", "English"),
        "site_url": industry.get("site_url", ""),
        "wp_url": os.getenv("WP_SITE", ""),
        "wp_username": os.getenv("WP_USER", ""),
        "wp_app_password": os.getenv("WP_APP_PASSWORD", ""),
    }

    print(f"开始生成: {project['name']} (mode={mode})")
    llm.reset_usage()

    result = generate_site(project, mode=mode, bypass_subscription=True)

    if result["ok"]:
        print(f"\n生成完成: {result['summary'].get('total_pages', 0)}/{len(industry.get('pages', []))} 页")
        for entry in result["pages"]:
            p = entry["page"]
            q = entry["quality"]
            print(f"  [{q.get('score', 0):.0f}] {p.get('slug', '?')}")
    else:
        print("\n生成失败。")

    if result.get("errors"):
        print(f"\n{len(result['errors'])} 个错误:")
        for err in result["errors"]:
            print(f"  - {err}")

    total = len(industry.get("pages", []))
    ok_count = result["summary"].get("total_pages", 0)
    if ok_count == total:
        print(f"\n[OK] All {total}/{total} pages generated successfully")
    else:
        print(f"\n[WARN] Only {ok_count}/{total} pages generated successfully")


# ── Phase 3: SEO Engine S0-S2 集成 ──────────────────────


def generate_blueprint_from_input(user_input: str,
                                  project_id: int = None,
                                  tenant_id: int = None) -> dict:
    """S0 → S1 → S2 完整管道。

    从自然语言输入生成 SiteBlueprint。

    Returns:
        {"ok": bool, "blueprint": SiteBlueprint dict, "profile": BusinessProfile dict}
    """
    try:
        from lib.seo_engine.stage0_clarify import clarify_request
        from lib.seo_engine.stage1_profile import build_business_profile
        from lib.seo_engine.stage2_blueprint import build_site_blueprint

        # S0: 需求澄清
        scope_result = clarify_request(user_input)
        scope = scope_result.get("scope", {})

        # S1: 生意画像
        project = None
        if project_id:
            from models import get_project
            project = get_project(project_id)
        # Inject tenant_id into project for profile building
        if project is None:
            project = {}
        if tenant_id and not project.get("tenant_id"):
            project["tenant_id"] = tenant_id

        profile = build_business_profile(scope, project)

        # S2: 站点蓝图
        blueprint = build_site_blueprint(
            project_id=project_id or 0,
            profile=profile,
        )

        return {
            "ok": True,
            "blueprint": blueprint.to_dict(),
            "profile": profile.to_dict(),
            "scope": scope,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_or_create_profile(project: dict = None,
                           user_input: str = None) -> dict:
    """获取或创建 BusinessProfile。

    如果 project 已有 business_profiles 记录,返回最新。
    否则从 user_input 或 project 字段创建新 profile。
    """
    if project and project.get("id"):
        try:
            from models import list_business_profiles
            profiles = list_business_profiles(project_id=project["id"])
            if profiles:
                bp = profiles[0]
                return {
                    "ok": True,
                    "profile_id": bp["id"],
                    "profile": bp["profile_json"],
                    "source": "existing",
                }
        except Exception:
            pass

    if user_input:
        scope = {"industry": user_input, "language": "English", "target_market": "global"}
        try:
            from lib.seo_engine.stage0_clarify import clarify_request
            scope_result = clarify_request(user_input)
            scope = scope_result.get("scope", scope)
        except Exception:
            pass

        from lib.seo_engine.stage1_profile import build_business_profile
        profile = build_business_profile(scope, project)

        if project and project.get("id"):
            try:
                from models import create_business_profile
                import json
                pid = create_business_profile(
                    tenant_id=project.get("tenant_id"),
                    project_id=project["id"],
                    status="draft",
                    profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
                )
                return {"ok": True, "profile_id": pid, "profile": profile.to_dict(), "source": "created"}
            except Exception:
                pass

        return {"ok": True, "profile": profile.to_dict(), "source": "transient"}

    return {"ok": False, "error": "需要 user_input 或已有 profile"}


def load_or_create_blueprint(project: dict = None,
                             profile=None) -> dict:
    # profile: dict | BusinessProfile
    """获取或创建 SiteBlueprint。

    如果 project 已有 site_blueprints 记录,返回最新。
    否则从 profile 创建新 blueprint。
    """
    if project and project.get("id"):
        try:
            from models import list_site_blueprints
            bps = list_site_blueprints(project_id=project["id"])
            if bps:
                bp = bps[0]
                return {
                    "ok": True,
                    "blueprint_id": bp["id"],
                    "blueprint": bp["blueprint_json"],
                    "source": "existing",
                }
        except Exception:
            pass

    if profile:
        # Convert dict to BusinessProfile if needed
        if isinstance(profile, dict):
            from lib.seo_engine.schemas import BusinessProfile
            profile = BusinessProfile.from_dict(profile)

        from lib.seo_engine.stage2_blueprint import build_site_blueprint
        bp = build_site_blueprint(
            project_id=project.get("id", 0) if project else 0,
            profile=profile,
        )

        if project and project.get("id"):
            try:
                from models import create_site_blueprint
                import json
                bpid = create_site_blueprint(
                    tenant_id=project.get("tenant_id"),
                    project_id=project["id"],
                    status="draft",
                    blueprint_json=json.dumps(bp.to_dict(), ensure_ascii=False),
                )
                return {"ok": True, "blueprint_id": bpid, "blueprint": bp.to_dict(), "source": "created"}
            except Exception:
                pass

        return {"ok": True, "blueprint": bp.to_dict(), "source": "transient"}

    return {"ok": False, "error": "需要 profile 或已有 blueprint"}


# ── Phase 4: Blueprint → PageContent 生成 ─────────────


def _industry_brief_from_pipeline_context(project: dict, profile):
    """Build or restore the brief used by the normal generation pipeline."""
    from lib.industry_brief import IndustryBrief, build_industry_brief

    stored = (project or {}).get("industry_brief")
    if isinstance(stored, IndustryBrief):
        return stored
    if isinstance(stored, dict) and stored.get("product"):
        return IndustryBrief.from_dict(stored)

    products = list(getattr(profile, "products", None) or [])
    buyers = list(getattr(profile, "buyer_personas", None) or [])
    markets = list(getattr(profile, "target_markets", None) or [])
    languages = list(getattr(profile, "languages", None) or [])
    product = (project or {}).get("seed_keyword") or (products[0] if products else "")
    industry = getattr(profile, "industry", "") or (project or {}).get("name", "")
    return build_industry_brief({
        "product": product or industry,
        "industry": industry or product,
        "audience": buyers[0] if buyers else "B2B buyers and distributors",
        "market": markets[0] if markets else "global export markets",
        "language": languages[0] if languages else "English",
    })


def _reinforce_page_contents_with_industry_brief(page_contents, brief):
    """Replace only weak/generic PageContent bodies with brief-driven copy."""
    from lib.page_content_writer import reinforce_page_content

    for page_content in page_contents or []:
        page = {
            "type": getattr(page_content, "page_type", "supplier_guide"),
            "page_type": getattr(page_content, "page_type", "supplier_guide"),
            "slug": getattr(page_content, "slug", ""),
            "title": getattr(page_content, "title", ""),
        }
        original = {
            "title": getattr(page_content, "title", ""),
            "meta_description": getattr(page_content, "meta_description", ""),
            "body_html": getattr(page_content, "body_html", ""),
        }
        reinforced = reinforce_page_content(original, page, brief)
        if reinforced != original:
            page_content.title = reinforced.get("title", page_content.title)
            page_content.meta_title = reinforced.get("title", getattr(page_content, "meta_title", ""))
            page_content.meta_description = reinforced.get("meta_description", page_content.meta_description)
            page_content.body_html = reinforced.get("body_html") or reinforced.get("html", page_content.body_html)
            if hasattr(page_content, "cta"):
                page_content.cta = reinforced.get("cta", page_content.cta)
    return page_contents


def generate_site_from_blueprint(project: dict, blueprint,
                                 mode: str = "dry-run",
                                 bypass_subscription: bool = False,
                                 max_pages: int = None,
                                 output_dir=None,
                                 progress_callback=None) -> dict:
    """从 SiteBlueprint 执行完整内容生成管线。

    Pipeline:
    1. 逐页 LLM 生成 → PageContent
    2. 内部链接注入
    3. Gutenberg 转换
    4. 质量审核
    5. 如需要,润色(score<70)
    6. Schema 生成
    7. Preview / Publish
    8. 写 page_contents / generations / generation_logs

    Args:
        max_pages: None=全量生成; >0=只生成前 N 页

    Returns 与 generate_site() 兼容的统一结构(含 truncated 标记)。
    """
    from lib.seo_engine.schemas import SiteBlueprint, PageContent, BusinessProfile
    from lib.seo_engine.stage3_generate import generate_pages_from_blueprint
    from lib.seo_engine.stage5_links import attach_links_to_pages
    from lib.gutenberg_emitter import page_content_to_gutenberg
    from lib.seo_engine.stage4_review import review_page_content, should_polish

    if isinstance(blueprint, dict):
        blueprint = SiteBlueprint.from_dict(blueprint)

    tenant_id = project.get("tenant_id")
    project_id = project.get("id", 0)
    bp_profile = blueprint.business_profile

    # Subscription check
    if tenant_id and not bypass_subscription:
        from lib.subscription import check_generation_allowed
        check = check_generation_allowed(tenant_id)
        if not check.get("allowed"):
            return {
                "ok": False, "code": "generation_failed",
                "message": f"额度检查失败: {check.get('reason')}",
                "pages_total": 0, "pages_success": 0, "pages_failed": 0,
                "truncated": False,
                "mode": mode, "usage": {}, "pages": [], "errors": [f"额度检查失败: {check.get('reason')}"],
                "retryable": False, "failed_generation_ids": [],
            }

    # Apply max_pages truncation
    all_bp_pages = list(blueprint.pages)
    total_available = len(all_bp_pages)
    truncated = False
    if max_pages is not None and max_pages > 0 and max_pages < total_available:
        blueprint.pages = all_bp_pages[:max_pages]
        truncated = True

    total = len(blueprint.pages)
    os.environ["CURRENT_DATE"] = _today_str()

    if progress_callback:
        progress_callback("stage", {"stage": "generating", "label": "逐页生成",
            "message": f"共 {total} 页, 开始生成…"})
        progress_callback("progress", {"current": 0, "total": total,
            "percent": 0, "elapsed": 0})

    # 1. 逐页生成
    page_contents = generate_pages_from_blueprint(blueprint, bp_profile)
    industry_brief = _industry_brief_from_pipeline_context(project, bp_profile)
    page_contents = _reinforce_page_contents_with_industry_brief(page_contents, industry_brief)

    # 2. 注入内部链接
    page_contents = attach_links_to_pages(page_contents, blueprint)

    # 3. Gutenberg + 4. Review + 5. Polish + Re-review
    all_results = []
    errors = []
    gen_ids = []
    failed_gen_ids = []
    persistence_errors_list = []

    for idx, pc in enumerate(page_contents):
        try:
            # ── page_start event ──
            if progress_callback:
                progress_callback("page_start", {
                    "slug": pc.slug,
                    "title": pc.title,
                    "index": idx + 1,
                    "total": total,
                    "status": "generating",
                })

            # Gutenberg
            gb = page_content_to_gutenberg(pc)
            if hasattr(pc, 'gutenberg_html'):
                pc.gutenberg_html = gb

            # ── page_preview event ──
            if progress_callback and (pc.body_html or gb):
                progress_callback("page_preview", {
                    "slug": pc.slug,
                    "title": pc.title,
                    "html": gb or pc.body_html,
                    "status": "preview",
                })

            # Review
            review = review_page_content(pc)

            # ── log score event ──
            if progress_callback:
                progress_callback("log", {
                    "level": "info" if review.get("ok") else "warning",
                    "message": f"{pc.slug}: 得分 {review.get('score', 0):.0f}/100 {'PASS' if review.get('ok') else 'NEEDS_POLISH'}",
                    "time": time.strftime("%H:%M:%S"),
                })

            # Polish if needed (score < 70)
            polish_attempted = False
            if should_polish(review):
                pg = {"slug": pc.slug, "type": pc.page_type, "target_keyword": pc.primary_keyword}
                ct = {"title": pc.title, "meta_description": pc.meta_description, "html": pc.body_html}
                ind = {"name": bp_profile.industry if bp_profile else "",
                       "language": bp_profile.languages[0] if bp_profile and bp_profile.languages else "English"}
                polished_ct, polished_q = polish_page(pg, ct, {"score": review["score"], "issues": review["issues"], "passed": review["ok"]}, ind)
                pc.body_html = polished_ct.get("html", pc.body_html)
                pc.meta_description = polished_ct.get("meta_description", pc.meta_description)
                polish_attempted = True

                # Re-review after polish
                review = review_page_content(pc)
                review["polished"] = True

                if progress_callback:
                    progress_callback("log", {
                        "level": "info",
                        "message": f"{pc.slug}: 已润色, 新得分 {review.get('score', 0):.0f}/100",
                        "time": time.strftime("%H:%M:%S"),
                    })

            # Quality gate: if still below threshold, flag
            if review.get("score", 0) < 70:
                review["ok"] = False
                if polish_attempted:
                    errors.append(f"{pc.slug}: score {review['score']:.0f} still <70 after polish")

            # Schema
            try:
                from lib.schema import jsonld_for
                site_url = project.get("site_url", "https://example.com")
                pc.schema_json = jsonld_for(
                    {"slug": pc.slug, "type": pc.page_type, "target_keyword": pc.primary_keyword},
                    {"title": pc.title, "meta_description": pc.meta_description, "html": pc.body_html},
                    site=site_url,
                    industry={"name": bp_profile.industry if bp_profile else "",
                              "seed_keyword": pc.primary_keyword,
                              "language": bp_profile.languages[0] if bp_profile and bp_profile.languages else "English"},
                )
            except Exception:
                pass

            # Record generation
            try:
                from models import create_generation
                gen_id = create_generation(
                    project_id=project_id, tenant_id=tenant_id,
                    status="completed", keyword=pc.primary_keyword,
                    page_type=pc.page_type, title=pc.title, slug=pc.slug,
                    quality_score=review.get("score", 0), page_count=1, passed_count=1,
                )
                gen_ids.append(gen_id)
            except Exception:
                gen_id = None

            # Save page_content
            persistence_ok = True
            persistence_error_msg = ""
            try:
                from models import create_page_content
                import json as _json
                create_page_content(
                    tenant_id=tenant_id, project_id=project_id,
                    slug=pc.slug, page_type=pc.page_type,
                    title=pc.title, primary_keyword=pc.primary_keyword,
                    content_json=_json.dumps(pc.to_dict(), ensure_ascii=False),
                    gutenberg_html=gb, quality_score=review.get("score", 0),
                    review_status="approved" if review.get("ok") else "needs_review",
                    generation_id=gen_id,
                )
            except Exception as exc:
                persistence_ok = False
                persistence_error_msg = str(exc)
                persistence_errors_list.append({
                    "slug": pc.slug,
                    "error": persistence_error_msg,
                    "step": "create_page_content",
                })
                # Log to generation_logs
                try:
                    from lib.generation_logs import log_generation_step
                    log_generation_step(
                        tenant_id=tenant_id, project_id=project_id,
                        generation_id=gen_id,
                        step="page_content_persist_failed",
                        status="failed",
                        message=f"PageContent 持久化失败: {persistence_error_msg}",
                        meta={"slug": pc.slug, "error": persistence_error_msg},
                    )
                except Exception:
                    pass

            all_results.append({
                "page": {"slug": pc.slug, "type": pc.page_type, "target_keyword": pc.primary_keyword, "gen_id": gen_id},
                "content": {"title": pc.title, "meta_description": pc.meta_description, "html": pc.body_html},
                "quality": {"score": review.get("score", 0), "passed": review.get("ok"), "issues": review.get("issues", [])},
            })

            # ── page_done event ──
            if progress_callback:
                progress_callback("page_done", {
                    "slug": pc.slug,
                    "title": pc.title,
                    "url": f"./{pc.slug}.html",
                    "score": review.get("score", 0),
                    "passed": review.get("ok", False),
                    "status": "done",
                })
                done_count = idx + 1
                progress_callback("progress", {
                    "current": done_count,
                    "total": total,
                    "percent": int(done_count / total * 100) if total > 0 else 0,
                })

        except Exception as e:
            errors.append(f"{pc.slug} 生成失败: {e}")
            if progress_callback:
                progress_callback("log", {
                    "level": "error",
                    "message": f"{getattr(pc, 'slug', 'unknown')}: 生成失败 — {e}",
                    "time": time.strftime("%H:%M:%S"),
                })
                progress_callback("page_done", {
                    "slug": getattr(pc, 'slug', 'unknown'),
                    "title": getattr(pc, 'title', 'Unknown'),
                    "status": "failed",
                    "error": str(e)[:200],
                })
            if hasattr(pc, 'slug'):
                try:
                    from models import create_generation
                    gid = create_generation(project_id=project_id, tenant_id=tenant_id,
                                           status="retry_pending", keyword=pc.primary_keyword,
                                           page_type=pc.page_type, title=pc.title, slug=pc.slug)
                    failed_gen_ids.append(gid)
                except Exception:
                    pass
            continue

    # 6a. Render HTML preview to output_src (for Canvas/frontend)
    if progress_callback:
        progress_callback("stage", {"stage": "quality", "label": "渲染预览",
            "message": f"正在生成 {len(all_results)} 页的 HTML 预览…"})
    site_url = project.get("site_url", "https://example.com")
    _write_preview(all_results, site_url, output_dir=output_dir)

    if progress_callback:
        progress_callback("stage", {"stage": "done", "label": "完成",
            "message": f"已生成 {len(all_results)}/{total} 页"})

    # 6b. Usage recording
    usage_info = {}
    if tenant_id and not bypass_subscription:
        try:
            from models import record_usage
            token_count = llm.last_usage().get("total_tokens", 0)
            page_count = len(all_results)
            if page_count > 0:
                record_usage(tenant_id, user_id=project.get("user_id"),
                           project_id=project_id, kind="generation", amount=page_count)
            if token_count > 0:
                record_usage(tenant_id, user_id=project.get("user_id"),
                           project_id=project_id, kind="token", amount=token_count)
            usage_info = {"pages": page_count, "tokens": token_count}
        except Exception:
            pass

    pages_success = len(all_results)
    pages_total = total
    pages_failed = pages_total - pages_success

    if pages_success == pages_total:
        code = "success"; ok = True; retryable = False
    elif pages_success > 0:
        code = "partial_success"; ok = False; retryable = True
    else:
        code = "generation_failed"; ok = False; retryable = len(failed_gen_ids) > 0

    # Build persistence warnings
    persistence_warnings = []
    if persistence_errors_list:
        persistence_warnings.append(
            f"{len(persistence_errors_list)} page(s) generated but NOT persisted to DB"
        )

    return {
        "ok": ok, "code": code,
        "message": f"{pages_success}/{pages_total} pages generated",
        "generation_ids": gen_ids,
        "failed_generation_ids": failed_gen_ids,
        "failed_page_slugs": [pc.slug for pc in page_contents if pc.review_status == "failed"],
        "project_id": project_id,
        "pages_total": pages_total, "pages_success": pages_success,
        "pages_failed": pages_failed, "truncated": truncated,
        "mode": mode, "usage": usage_info, "retryable": retryable,
        "pages": all_results, "errors": errors,
        "persistence_errors": persistence_errors_list,
        "warnings": persistence_warnings,
        "summary": {"total_pages": pages_success, "errors": len(errors)},
    }


def generate_site_from_input(user_input: str, project_id: int = None,
                             tenant_id: int = None, mode: str = "dry-run",
                             bypass_subscription: bool = False,
                             max_pages: int = None,
                             use_competitor: bool = False,
                             competitor_query: str = None,
                             competitor_urls: list[str] = None,
                             output_dir=None,
                             progress_callback=None) -> dict:
    """从自然语言输入执行完整 S0 → PageContent 管线。

    Phase 5.1: 可选竞品分析增强 (use_competitor=True)。
    """
    from lib.seo_engine.stage0_clarify import clarify_request
    from lib.seo_engine.stage1_profile import build_business_profile
    from lib.seo_engine.stage2_blueprint import build_site_blueprint

    # S0
    if progress_callback:
        progress_callback("stage", {"stage": "planning", "label": "需求分析",
            "message": "S0 正在澄清你的需求…"})
    scope_result = clarify_request(user_input)
    scope = scope_result.get("scope", {})

    if progress_callback:
        progress_callback("log", {"level": "info",
            "message": f"已识别行业: {scope.get('industry', '未知')}, 语言: {scope.get('language', 'English')}",
            "time": time.strftime("%H:%M:%S")})

    # S1
    if progress_callback:
        progress_callback("stage", {"stage": "serp", "label": "生意画像",
            "message": "S1 正在构建生意画像…"})
    project = None
    if project_id:
        from models import get_project
        project = get_project(project_id)
    if project is None:
        project = {}
    if tenant_id and not project.get("tenant_id"):
        project["tenant_id"] = tenant_id
    profile = build_business_profile(scope, project)

    # Phase 9.4.0: consume (without replacing) the open-vocabulary intent and
    # language-normalizer output, then carry a deterministic content brief into S3.
    from lib.intent_engine import empty_intent, merge_intent
    from lib.industry_brief import build_industry_brief
    from lib.generation_plan import apply_b2b_content_defaults
    content_intent = apply_b2b_content_defaults(merge_intent(empty_intent(), user_input))
    if not content_intent.get("product"):
        content_intent["product"] = (profile.products[0] if profile.products else scope.get("industry"))
    if not content_intent.get("industry"):
        content_intent["industry"] = profile.industry or scope.get("industry")
    if not content_intent.get("audience"):
        content_intent["audience"] = profile.buyer_personas[0] if profile.buyer_personas else "B2B buyers and distributors"
    if not content_intent.get("market"):
        content_intent["market"] = profile.target_markets[0] if profile.target_markets else scope.get("target_market")
    if not content_intent.get("language"):
        content_intent["language"] = profile.languages[0] if profile.languages else scope.get("language", "English")
    industry_brief = build_industry_brief(content_intent)

    # Optional: competitor analysis → hints
    competitor_hints = None
    if use_competitor:
        try:
            cq = competitor_query or user_input
            report = analyze_competitor_seo(
                query=cq, project_id=project_id, tenant_id=tenant_id,
                urls=competitor_urls,
            )
            if report.get("surpass_strategy"):
                from lib.surpass_strategy import strategy_to_blueprint_hints
                ss_dict = report["surpass_strategy"]
                from lib.surpass_strategy import SurpassStrategy as SS
                ss = SS(**{k: v for k, v in ss_dict.items() if k in SS.__dataclass_fields__})
                competitor_hints = strategy_to_blueprint_hints(ss)
        except Exception:
            pass

    # S2
    if progress_callback:
        progress_callback("stage", {"stage": "blueprint", "label": "站点蓝图",
            "message": "S2 正在规划页面结构…"})
    blueprint = build_site_blueprint(
        project_id=project_id or 0, profile=profile,
        competitor_hints=competitor_hints,
    )

    if progress_callback:
        total_pages = len(blueprint.pages)
        progress_callback("log", {"level": "info",
            "message": f"蓝图完成: {total_pages} 页, {len(blueprint.pillar_pages)} pillar + {len(blueprint.cluster_pages)} cluster",
            "time": time.strftime("%H:%M:%S")})

    # Phase 4 generation
    gen_project = {
        "id": project_id or 0,
        "tenant_id": tenant_id,
        "user_id": project.get("user_id"),
        "name": scope.get("industry", "Generated"),
        "site_url": project.get("site_url", ""),
        "industry_brief": industry_brief.to_dict(),
    }
    return generate_site_from_blueprint(gen_project, blueprint, mode=mode,
                                        bypass_subscription=bypass_subscription,
                                        max_pages=max_pages,
                                        output_dir=output_dir,
                                        progress_callback=progress_callback)


# ── Phase 5: 竞品 SEO 分析 ─────────────────────────────


_GENERIC_COMPETITOR_TOKENS = {
    "best", "b2b", "buyer", "buyers", "compare", "comparison", "export",
    "global", "guide", "manufacturer", "market", "supplier", "top",
    "wholesale",
}


def _validate_mock_report_topic(query: str, report_dict: dict) -> None:
    """Reject mock reports whose generated topic does not match the query."""
    import json as _json
    import re as _re

    query_tokens = set(_re.findall(r"[a-z0-9]+", str(query or "").lower()))
    payload = {
        "serp_results": report_dict.get("serp_results", []),
        "competitors": report_dict.get("competitors", []),
    }
    report_text = _json.dumps(payload, ensure_ascii=False).lower()

    if "leather" not in query_tokens and any(marker in report_text for marker in (
        "pu leather", "synthetic leather", "pvc leather", "pu-leather",
    )):
        raise ValueError("mock report topic mismatch: leather content does not match query")

    topic_tokens = {
        token for token in query_tokens
        if len(token) >= 3 and token not in _GENERIC_COMPETITOR_TOKENS
    }
    report_tokens = set(_re.findall(r"[a-z0-9]+", report_text))
    if topic_tokens and not topic_tokens.intersection(report_tokens):
        raise ValueError("mock report topic mismatch: generated content does not match query")


def analyze_competitor_seo(query: str, project_id: int = None,
                           tenant_id: int = None, urls: list[str] = None,
                           market: str = None, language: str = None,
                           limit: int = 10) -> dict:
    """执行竞品 SEO 分析 (mock 默认)。

    Pipeline:
    1. SERP search → competitor_analysis
    2. gap_analyzer → GapMatrix
    3. surpass_strategy → SurpassStrategy
    4. Save competitor_reports

    Returns CompetitorReport.to_dict()
    """
    from lib.competitor_analysis import analyze_competitors
    from lib.gap_analyzer import build_gap_matrix
    from lib.surpass_strategy import build_surpass_strategy

    provider = "manual" if urls else "mock"

    # 1. 竞品分析 (mock 模式不真实抓取)
    report = analyze_competitors(
        query=query, market=market, language=language,
        urls=urls, limit=limit, tenant_id=tenant_id, project_id=project_id,
        provider_name=provider,
    )

    # 2. Gap matrix
    gap = build_gap_matrix(report.competitors)
    report.gap_matrix = gap

    # 3. Surpass strategy
    strategy = build_surpass_strategy(query, gap, report.competitors)
    report.surpass_strategy = strategy

    report_dict = report.to_dict()
    if provider == "mock":
        _validate_mock_report_topic(query, report_dict)

    # 4. Save to DB
    try:
        from models import create_competitor_report
        import json as _json
        report_id = create_competitor_report(
            tenant_id=tenant_id, project_id=project_id,
            query=query, market=market or "global",
            language=language or "English",
            status=report.status,
            report_json=_json.dumps(report_dict, ensure_ascii=False),
        )
        report.id = report_id
    except Exception:
        pass

    return report.to_dict()


def generate_blueprint_with_competitor_input(user_input: str,
                                             project_id: int = None,
                                             tenant_id: int = None,
                                             query: str = None,
                                             urls: list[str] = None,
                                             market: str = None,
                                             language: str = None,
                                             limit: int = 10) -> dict:
    """Phase 5.1: 竞品分析 → Blueprint Hints → 增强 SiteBlueprint。

    Pipeline:
    1. analyze_competitor_seo → CompetitorReport + SurpassStrategy
    2. strategy_to_blueprint_hints → structured hints
    3. S0 clarify → scope
    4. S1 profile → BusinessProfile
    5. S2 blueprint → SiteBlueprint (with competitor_hints)
    6. Save blueprint + return
    """
    from lib.surpass_strategy import strategy_to_blueprint_hints

    # 1. 竞品分析
    competitor_query = query or user_input
    report = analyze_competitor_seo(
        query=competitor_query, project_id=project_id, tenant_id=tenant_id,
        urls=urls, market=market, language=language, limit=limit,
    )

    # 2. Strategy → hints
    hints = strategy_to_blueprint_hints(
        _dict_to_strategy(report.get("surpass_strategy", {}))
    ) if report.get("surpass_strategy") else None

    # 3-5. S0 → S1 → S2
    from lib.seo_engine.stage0_clarify import clarify_request
    from lib.seo_engine.stage1_profile import build_business_profile
    from lib.seo_engine.stage2_blueprint import build_site_blueprint

    scope_result = clarify_request(user_input)
    scope = scope_result.get("scope", {})

    profile = build_business_profile(scope)

    blueprint = build_site_blueprint(
        project_id=project_id or 0, profile=profile,
        competitor_hints=hints,
    )
    blueprint.competitor_hints = hints
    blueprint.source_competitor_report_id = report.get("id")

    # 6. Save blueprint
    blueprint_id = None
    try:
        from models import create_site_blueprint
        import json as _json
        blueprint_id = create_site_blueprint(
            tenant_id=tenant_id, project_id=project_id,
            blueprint_json=_json.dumps(blueprint.to_dict(), ensure_ascii=False),
        )
    except Exception:
        pass

    return {
        "ok": True,
        "competitor_report_id": report.get("id"),
        "blueprint_id": blueprint_id,
        "pages_total": len(blueprint.pages),
        "pages": [p.to_dict() for p in blueprint.pages],
        "hints_applied": hints is not None,
    }


def _dict_to_strategy(d: dict):
    """Convert dict to SurpassStrategy for hints generation。"""
    if not d:
        return None
    from lib.surpass_strategy import SurpassStrategy as SS
    return SS(
        target_keyword=d.get("target_keyword", ""),
        recommended_pages=d.get("recommended_pages", []),
        recommended_sections=d.get("recommended_sections", []),
        recommended_faq=d.get("recommended_faq", []),
        recommended_schema=d.get("recommended_schema", []),
        recommended_internal_links=d.get("recommended_internal_links", []),
        content_angle=d.get("content_angle", ""),
        differentiation_points=d.get("differentiation_points", []),
        priority_score=d.get("priority_score", 0),
        rationale=d.get("rationale", ""),
    )


# ── Phase 9.2: Job Mode ───────────────────────────────


def create_real_llm_generation_job(tenant_id: int, project_id: int = None,
                                   user_input: str = None,
                                   blueprint_id: int = None,
                                   mode: str = "dry-run",
                                   use_competitor: bool = False,
                                   bypass_subscription: bool = False) -> dict:
    from lib.generation_job_mode import create_generation_job
    return create_generation_job(
        tenant_id=tenant_id, project_id=project_id,
        user_input=user_input, blueprint_id=blueprint_id,
        mode=mode, use_competitor=use_competitor,
        bypass_subscription=bypass_subscription,
    )


def run_real_llm_generation_job(job_id: int, tenant_id: int = None) -> dict:
    from lib.generation_job_mode import run_generation_job
    return run_generation_job(job_id, tenant_id=tenant_id)


# ── Phase 6: 发布运营 ─────────────────────────────────


def sync_generated_site(project_id: int, tenant_id: int,
                        dry_run: bool = True, mode: str = "draft") -> dict:
    """同步当前项目所有 page_contents 到 CMS。"""
    from lib.publish_sync import sync_project_pages
    return sync_project_pages(
        project_id=project_id, tenant_id=tenant_id,
        cms_type="wordpress", mode=mode, dry_run=dry_run,
    )


def rollback_last_sync(project_id: int, tenant_id: int,
                       dry_run: bool = True) -> dict:
    """回滚项目最近同步。"""
    from lib.publish_rollback import rollback_project
    from lib.publish_snapshot import list_publish_snapshots
    snaps = list_publish_snapshots(project_id=project_id, tenant_id=tenant_id)
    snap_ids = [s["id"] for s in snaps[:1]] if snaps else []
    if not snap_ids:
        return {"ok": False, "error": "No snapshots found for this project"}
    return rollback_project(project_id, tenant_id, snap_ids, dry_run=dry_run)


if __name__ == "__main__":
    main()
