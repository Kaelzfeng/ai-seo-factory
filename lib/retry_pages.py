# -*- coding: utf-8 -*-
"""lib/retry_pages.py · 失败页补跑

Phase 1.1: 支持 retry_generation_page / retry_failed_pages
- 只能补跑 failed / retry_pending 的页面
- 补跑前写 generation_logs: retrying
- 补跑成功写 recovered
- 补跑失败继续记录明确原因
- 不影响已成功页面
- 不重复扣除已成功页面的 generation usage
"""

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _get_generation(gen_id: int) -> dict | None:
    """获取 generation 记录。"""
    try:
        from models import list_generations
        gens = list_generations()
        for g in gens:
            if g["id"] == gen_id:
                return dict(g)
    except Exception:
        pass
    return None


def _can_retry(status: str) -> bool:
    """检查状态是否允许重试。"""
    return status in ("failed", "retry_pending")


def retry_generation_page(generation_id: int,
                          project: dict = None,
                          industry: dict = None,
                          mode: str = "dry-run",
                          bypass_subscription: bool = False) -> dict:
    """补跑单页 generation。

    Args:
        generation_id: generation 记录 ID
        project: 项目 dict (含 industry_config, tenant_id 等)
        industry: 行业配置 dict (含 seed_keyword, language, tone 等)
        mode: "dry-run" | "publish"
        bypass_subscription: CLI 模式跳过额度

    Returns:
        {"ok": True/False, "generation_id": ..., "gen_id": ...,
         "action": "recovered"|"failed"|"skipped", "error": ...}
    """
    gen = _get_generation(generation_id)
    if gen is None:
        return {"ok": False, "generation_id": generation_id,
                "action": "failed", "error": "Generation 记录不存在"}

    current_status = gen.get("status", "")
    if not _can_retry(current_status):
        return {"ok": True, "generation_id": generation_id,
                "action": "skipped",
                "error": f"状态为 {current_status},无需补跑"}

    tenant_id = gen.get("tenant_id")
    project_id = gen.get("project_id", project.get("id", 0) if project else 0)
    page_type = gen.get("page_type", "guide")
    target_kw = gen.get("keyword", "")
    page_slug = gen.get("slug", "")

    # 构建 page_plan
    page_plan = {
        "type": page_type,
        "target_keyword": target_kw,
        "slug": page_slug,
        "title": gen.get("title", target_kw),
    }

    # 构建 industry (优先用传入的)
    if industry is None:
        industry = {}
    seed = industry.get("seed_keyword", target_kw)
    org_name = industry.get("org_name", project.get("name", "Demo Co.") if project else "Demo Co.")
    today = time.strftime("%Y-%m-%d")

    # ── 标记 retrying ──
    try:
        from models import update_generation
        update_generation(generation_id, status="retrying")
    except Exception:
        pass

    try:
        from lib.generation_logs import log_generation_step
        log_generation_step(
            tenant_id=tenant_id, project_id=project_id,
            generation_id=generation_id, step="retry",
            status="running", message="开始补跑",
            meta={"page_type": page_type, "keyword": target_kw, "slug": page_slug},
        )
    except Exception:
        pass

    # ── 执行生成 ──
    try:
        import run as _run

        os.environ["CURRENT_DATE"] = today

        gen_result = _run._generate_page_content(
            page_plan, industry, seed, org_name, today,
            page_index=0, total_pages=1,
        )
        content = gen_result["content"]
        page = gen_result["page"]

        # 质量评分
        q_result = _run._score_page(page, content, industry)

        # 润色
        content, q_result = _run._polish_if_needed(page, content, q_result, industry)

        # 更新 generation 为 recovered
        try:
            from models import update_generation
            update_generation(
                generation_id, status="recovered",
                title=content.get("title", gen.get("title", "")),
                quality_score=q_result.get("score", 0.0),
                passed_count=1 if q_result.get("passed") else 0,
            )
        except Exception:
            pass

        # 写 recovered 日志
        try:
            from lib.generation_logs import log_generation_step
            log_generation_step(
                tenant_id=tenant_id, project_id=project_id,
                generation_id=generation_id, step="recovered",
                status="success",
                message=f"补跑成功: score={q_result.get('score', 0):.0f}",
                meta={"score": q_result.get("score"), "passed": q_result.get("passed")},
            )
            from lib.generation_logs import mark_generation_success
            mark_generation_success(generation_id, meta={"recovered": True})
        except Exception:
            pass

        # 记录补跑成功的 generation usage
        if tenant_id and not bypass_subscription:
            try:
                from models import record_usage
                record_usage(tenant_id, user_id=project.get("user_id") if project else None,
                           project_id=project_id, kind="generation", amount=1)
            except Exception:
                pass

        # Token usage 始终记录
        if tenant_id and not bypass_subscription:
            try:
                usage = _run.llm.last_usage()
                token_count = usage.get("total_tokens", 0)
                if token_count > 0:
                    from models import record_usage
                    record_usage(tenant_id, user_id=project.get("user_id") if project else None,
                               project_id=project_id, kind="token", amount=token_count)
            except Exception:
                pass

        return {
            "ok": True,
            "generation_id": generation_id,
            "gen_id": generation_id,
            "action": "recovered",
            "content": content,
            "quality": q_result,
            "page": page,
        }

    except Exception as e:
        # 补跑失败: 恢复为 failed 状态并记录原因
        try:
            from models import update_generation
            update_generation(generation_id, status="failed")
        except Exception:
            pass

        try:
            from lib.generation_logs import mark_generation_failed
            mark_generation_failed(
                generation_id, step="retry",
                reason=str(e),
                meta={"page_type": page_type, "keyword": target_kw},
            )
        except Exception:
            pass

        return {
            "ok": False,
            "generation_id": generation_id,
            "action": "failed",
            "error": str(e),
        }


def retry_failed_pages(project: dict = None,
                       project_id: int = None,
                       generation_ids: list = None,
                       industry: dict = None,
                       mode: str = "dry-run",
                       bypass_subscription: bool = False) -> dict:
    """批量补跑失败页面。

    Args:
        project: 项目 dict
        project_id: 项目 ID (如 project=None)
        generation_ids: 指定要补跑的 generation ID 列表(为空则自动查)
        industry: 行业配置 dict
        mode: "dry-run" | "publish"
        bypass_subscription: CLI 模式跳过额度

    Returns:
        {"ok": bool, "results": [...], "summary": {"total": N, "recovered": N, "failed": N, "skipped": N}}
    """
    # 读取行业配置
    if industry is None and project and project.get("industry_config"):
        import yaml
        config_path = project["industry_config"]
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as fh:
                industry = yaml.safe_load(fh)

    if industry is None:
        industry = {}

    # 如果没有指定 generation_ids,从 project 查询 retry_pending/failed
    if not generation_ids and project_id:
        try:
            from models import list_generations
            gens = list_generations(project_id=project_id)
            generation_ids = [g["id"] for g in gens if _can_retry(g.get("status", ""))]
        except Exception:
            generation_ids = []

    if not generation_ids:
        return {"ok": True, "results": [],
                "summary": {"total": 0, "recovered": 0, "failed": 0, "skipped": 0}}

    results = []
    for gen_id in generation_ids:
        res = retry_generation_page(
            generation_id=gen_id,
            project=project,
            industry=industry,
            mode=mode,
            bypass_subscription=bypass_subscription,
        )
        results.append(res)

    summary = {
        "total": len(results),
        "recovered": sum(1 for r in results if r["action"] == "recovered"),
        "failed": sum(1 for r in results if r["action"] == "failed"),
        "skipped": sum(1 for r in results if r["action"] == "skipped"),
    }
    ok = summary["failed"] == 0

    return {"ok": ok, "results": results, "summary": summary}
