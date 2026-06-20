#!/usr/bin/env bash
set -e
echo "=== AI SEO Content Factory Server Bootstrap ==="
echo "Target: Ubuntu 22.04+ / Debian 12+"

# System packages
sudo apt update -qq
sudo apt install -y -qq python3 python3-venv python3-pip nginx git curl

# Create dirs
PROJECT_DIR=${1:-$(pwd)}
mkdir -p "$PROJECT_DIR/instance" "$PROJECT_DIR/logs" "$PROJECT_DIR/.cache" "$PROJECT_DIR/backups"

# Python venv
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
fi
source "$PROJECT_DIR/.venv/bin/activate"
pip install -q -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || echo "[WARN] pip install may need retry"

# Check
cd "$PROJECT_DIR"
python scripts/check_config.py
python scripts/dev_bootstrap.py

echo ""
echo "=== Done ==="
echo "Next: cp deploy/env.production.example .env && vi .env"
echo "Then: bash scripts/start_gunicorn.sh"
