#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill old server if running
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

echo "==> Blackbox API (--reload)"
echo "    http://localhost:8000/health"
echo ""

cd "$DIR"
# Source .env for CONCURRENCY, API key, etc.
set -a; source .env; set +a

uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
