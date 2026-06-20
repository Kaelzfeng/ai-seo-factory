#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/run_batch.py · 批量任务 CLI 入口

用法:
    python scripts/run_batch.py --csv examples/batch.csv --project-id 1 --mode dry-run
    python scripts/run_batch.py --batch-id 1 --run
    python scripts/run_batch.py --batch-id 1 --retry-failed
    python scripts/run_batch.py --batch-id 1 --retry-partial
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _print_summary(data: dict, label: str = ""):
    """打印可读摘要。"""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    s = data.get("summary", {})
    if not s:
        s = data
    print(f"  batch_id:     {data.get('batch_run_id', 'N/A')}")
    print(f"  status:       {s.get('status', 'N/A')}")
    print(f"  total_jobs:   {s.get('total', s.get('total_jobs', 0))}")
    print(f"  success_jobs: {s.get('success', s.get('success_jobs', 0))}")
    print(f"  failed_jobs:  {s.get('failed', s.get('failed_jobs', 0))}")
    print(f"  partial_jobs: {s.get('partial', s.get('partial_jobs', 0))}")


def cmd_import(args):
    """导入 CSV → 创建 batch_run + jobs"""
    from lib.batch_jobs import parse_batch_csv, create_batch_run, create_jobs_from_rows
    from models import get_project

    proj = get_project(args.project_id)
    if proj is None:
        print(f"项目 {args.project_id} 不存在")
        sys.exit(1)

    # 解析 CSV
    try:
        rows = parse_batch_csv(args.csv)
    except ValueError as e:
        print(f"CSV 解析错误: {e}")
        sys.exit(1)

    print(f"CSV 解析完成: {len(rows)} 行")

    # 创建 batch_run
    csv_name = Path(args.csv).stem
    br = create_batch_run(
        tenant_id=proj.get("tenant_id") or 0,
        user_id=proj.get("user_id"),
        project_id=args.project_id,
        name=f"{csv_name} ({args.mode})",
        source=args.csv,
        mode=args.mode,
    )
    bid = br["id"]
    print(f"Batch run 创建: id={bid}")

    # 创建 jobs
    created = create_jobs_from_rows(
        batch_run_id=bid,
        tenant_id=proj.get("tenant_id") or 0,
        user_id=proj.get("user_id"),
        project_id=args.project_id,
        rows=rows,
        mode=args.mode,
    )
    print(f"Jobs 创建: {len(created)} 个")

    _print_summary({"batch_run_id": bid, "summary": {"total": len(created), "status": "created"}})

    # ── 清晰提示下一步 ──
    print()
    print(f"  Next:")
    print(f"    python scripts/run_batch.py --batch-id {bid} --run")
    if args.mode == "dry-run":
        print(f"  (dry-run 模式默认 bypass subscription, 不计用量)")
    else:
        print(f"  (publish 模式, 如需跳过额度检查请加 --bypass-subscription)")

    return bid


def cmd_run(args):
    """运行 batch"""
    from lib.batch_runner import run_batch

    bypass = args.bypass_subscription or args.mode == "dry-run"
    result = run_batch(args.batch_id, bypass_subscription=bypass,
                       max_jobs=args.max_jobs)
    if result.get("error"):
        print(f"错误: {result['error']}")
        sys.exit(1)

    # ── 逐 job 输出详情 ──
    for r in result.get("results", []):
        jid = r.get("job_id", "?")
        st = r.get("status", "?")
        ps = r.get("pages_success", 0)
        pt = r.get("pages_total", 0)
        err = r.get("error", "")
        flag = "[OK]" if r.get("ok") else "[FAIL]"
        detail = f"{flag} job_id={jid} status={st} pages={ps}/{pt}"
        if err:
            detail += f" error={err[:80]}"
        print(f"  {detail}")

    _print_summary(result, "Batch Run 结果")


def cmd_retry_failed(args):
    """重试失败 job"""
    from lib.batch_runner import retry_failed_jobs

    bypass = args.bypass_subscription or args.mode == "dry-run"
    result = retry_failed_jobs(args.batch_id, bypass_subscription=bypass)
    if result.get("error"):
        print(f"错误: {result['error']}")
        sys.exit(1)

    for r in result.get("results", []):
        jid = r.get("job_id", "?")
        st = r.get("status", "?")
        flag = "[OK]" if r.get("ok") else "[FAIL]"
        print(f"  {flag} job_id={jid} status={st}")

    _print_summary(result, "Retry Failed 结果")


def cmd_retry_partial(args):
    """补跑 partial job 的失败页"""
    from lib.batch_runner import retry_partial_jobs

    bypass = args.bypass_subscription or args.mode == "dry-run"
    result = retry_partial_jobs(args.batch_id, bypass_subscription=bypass)
    if result.get("error"):
        print(f"错误: {result['error']}")
        sys.exit(1)

    for r in result.get("results", []):
        jid = r.get("job_id", "?")
        action = r.get("action", "?")
        rs = r.get("retry_summary", {})
        flag = "[OK]" if r.get("ok") else "[FAIL]"
        detail = f"{flag} job_id={jid} action={action}"
        if rs:
            detail += f" recovered={rs.get('recovered', 0)}/{rs.get('total', 0)}"
        print(f"  {detail}")

    _print_summary(result, "Retry Partial 结果")


def main():
    parser = argparse.ArgumentParser(description="批量内容生成 CLI")
    sub = parser.add_subparsers(dest="command")

    # import
    p_import = sub.add_parser("import", help="从 CSV 导入批量任务")
    p_import.add_argument("--csv", required=True, help="CSV 文件路径")
    p_import.add_argument("--project-id", type=int, required=True, help="项目 ID")
    p_import.add_argument("--mode", default="dry-run", choices=["dry-run", "publish"])

    # run
    p_run = sub.add_parser("run", help="执行批量任务")
    p_run.add_argument("--batch-id", type=int, required=True, help="Batch Run ID")
    p_run.add_argument("--mode", default="dry-run", choices=["dry-run", "publish"])
    p_run.add_argument("--max-jobs", type=int, default=None, help="最大执行数")
    p_run.add_argument("--bypass-subscription", action="store_true",
                       help="跳过 SaaS 额度检查")

    # retry-failed
    p_rf = sub.add_parser("retry-failed", help="重试失败 job")
    p_rf.add_argument("--batch-id", type=int, required=True, help="Batch Run ID")
    p_rf.add_argument("--mode", default="dry-run", choices=["dry-run", "publish"])
    p_rf.add_argument("--bypass-subscription", action="store_true")

    # retry-partial
    p_rp = sub.add_parser("retry-partial", help="补跑 partial job 的失败页")
    p_rp.add_argument("--batch-id", type=int, required=True, help="Batch Run ID")
    p_rp.add_argument("--mode", default="dry-run", choices=["dry-run", "publish"])
    p_rp.add_argument("--bypass-subscription", action="store_true")

    args = parser.parse_args()

    if args.command == "import":
        cmd_import(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "retry-failed":
        cmd_retry_failed(args)
    elif args.command == "retry-partial":
        cmd_retry_partial(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
