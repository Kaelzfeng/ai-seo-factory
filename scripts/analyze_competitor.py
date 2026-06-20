#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/analyze_competitor.py · Phase 5: 竞品分析 CLI

用法:
    python scripts/analyze_competitor.py "PU leather supplier" --mock
    python scripts/analyze_competitor.py "PU leather supplier" --urls urls.txt
    python scripts/analyze_competitor.py "PU leather supplier" --project-id 1
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="竞品 SEO 分析")
    parser.add_argument("query", help="关键词")
    parser.add_argument("--mock", action="store_true", default=True, help="使用 mock provider (默认)")
    parser.add_argument("--urls", help="URL 列表文件 (每行一个)")
    parser.add_argument("--project-id", type=int, help="项目 ID")
    parser.add_argument("--market", default="global")
    parser.add_argument("--language", default="English")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    urls = None
    provider = "mock"
    if args.urls:
        with open(args.urls, "r", encoding="utf-8") as fh:
            urls = [line.strip() for line in fh if line.strip()]
        provider = "manual"

    from lib.competitor_analysis import analyze_competitors
    from lib.gap_analyzer import build_gap_matrix
    from lib.surpass_strategy import build_surpass_strategy

    print(f"Analyzing: {args.query}")
    print(f"Provider: {provider} | Limit: {args.limit}")

    report = analyze_competitors(
        query=args.query, market=args.market, language=args.language,
        urls=urls, limit=args.limit, provider_name=provider,
        project_id=args.project_id,
    )

    # Gap matrix
    gap = build_gap_matrix(report.competitors)
    report.gap_matrix = gap

    # Surpass strategy
    strategy = build_surpass_strategy(args.query, gap, report.competitors)
    report.surpass_strategy = strategy

    # ── 输出 ──
    print(f"\n{'='*60}")
    print(f"  Competitor Analysis Report")
    print(f"{'='*60}")
    print(f"  Query:          {report.query}")
    print(f"  SERP Results:   {len(report.serp_results)}")
    print(f"  Analyzed:       {len([c for c in report.competitors if not c.error])}")
    print(f"  Failed:         {len([c for c in report.competitors if c.error])}")
    print(f"  Status:         {report.status}")
    print()

    print(f"  Top 5 Keyword Gaps:")
    for kw in gap.keyword_gaps[:5]:
        print(f"    - {kw}")

    print(f"\n  Top 5 Topic Gaps:")
    for tp in gap.topic_gaps[:5]:
        print(f"    - {tp}")

    print(f"\n  Recommended Pages:")
    for rp in strategy.recommended_pages[:5]:
        print(f"    - {rp}")

    print(f"\n  Recommended FAQ:")
    for rf in strategy.recommended_faq[:3]:
        print(f"    - {rf}")

    print(f"\n  Strategy Priority: {strategy.priority_score:.0f}/100")
    print(f"  Content Angle: {strategy.content_angle[:120]}...")
    print(f"\n  Rationale: {strategy.rationale[:200]}...")


if __name__ == "__main__":
    main()
