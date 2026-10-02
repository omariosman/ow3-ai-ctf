#!/usr/bin/env bash
# Non-Docker local development runner (plan section 7).
# Starts the FastAPI backend and the Next.js frontend together.
#
#   ./dev.sh
#
# Backend -> http://localhost:8000   Frontend -> http://localhost:3000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo
  echo "Shutting down…"
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- Backend ---
echo "==> Setting up backend"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "==> Starting backend on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &

# --- Frontend ---
echo "==> Setting up frontend"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi

echo "==> Starting frontend on http://localhost:3000"
NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-http://localhost:8000}" npm run dev &

wait
