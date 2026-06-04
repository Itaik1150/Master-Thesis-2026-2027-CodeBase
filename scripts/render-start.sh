#!/usr/bin/env bash
# Render start: run Lexi API and proactive scheduler on one instance
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Starting Lexi Node server..."
(cd "$ROOT/Lexi/server" && node build/server.js) &
NODE_PID=$!

echo "==> Starting proactive scheduler (logic-python)..."
(cd "$ROOT/logic-python" && python scheduler.py) &
PY_PID=$!

cleanup() {
  echo "==> Shutting down..."
  kill "$NODE_PID" "$PY_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# If either process exits, stop the service (Render will restart)
wait -n "$NODE_PID" "$PY_PID"
EXIT_CODE=$?
cleanup
exit "$EXIT_CODE"
