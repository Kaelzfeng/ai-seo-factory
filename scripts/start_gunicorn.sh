#!/usr/bin/env bash
set -e
PROJECT_DIR=${1:-$(pwd)}
cd "$PROJECT_DIR"

# Check venv
if [ ! -d ".venv" ]; then
    echo "ERROR: .venv not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check SECRET_KEY
if grep -q "dev-secret-change-in-production" .env 2>/dev/null || [ -z "${SECRET_KEY}" ]; then
    echo "WARNING: SECRET_KEY is using default value. Set a strong key in .env or environment."
fi

source .venv/bin/activate
mkdir -p logs

BIND=${GUNICORN_BIND:-127.0.0.1:8000}
echo "Starting gunicorn on $BIND"
exec .venv/bin/gunicorn -c deploy/gunicorn.conf.py app:app
