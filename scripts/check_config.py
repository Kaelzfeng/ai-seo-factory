#!/usr/bin/env python
"""scripts/check_config.py · Phase 8: 配置检查"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    p = argparse.ArgumentParser(); p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    from lib.config_check import validate_runtime_config, load_runtime_config
    cfg = validate_runtime_config(args.strict)
    print(f"Environment: {cfg['environment']}")
    print(f"OK: {cfg['ok']}")
    for svc, info in cfg["services"].items():
        print(f"  {svc}: {info}")
    llm = cfg["services"]["llm"]
    print(f"  LLM provider: {llm['provider']} (configured={llm['configured']}, model={llm['model']})")
    if cfg.get("warnings"): print(f"Warnings: {cfg['warnings']}")
    if cfg.get("errors"): print(f"Errors: {cfg['errors']}")
    sys.exit(0 if cfg["ok"] else 1)

if __name__ == "__main__": main()
