#!/usr/bin/env python
"""scripts/beta_report.py · Phase 9.3: Beta Report CLI"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tenant-id", type=int, default=1)
    p.add_argument("--project-id", type=int)
    p.add_argument("--out")
    args = p.parse_args()

    from lib.beta_report import generate_private_beta_report, beta_report_to_markdown
    report = generate_private_beta_report(args.tenant_id, args.project_id)
    md = beta_report_to_markdown(report)
    print(md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f: f.write(md)
        print(f"\nSaved to {args.out}")

if __name__ == "__main__": main()
