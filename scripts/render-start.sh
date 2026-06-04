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

# If scheduler crashes on startup (e.g. missing Firebase env), keep Lexi API running
sleep 3
if ! kill -0 "$PY_PID" 2>/dev/null; then
  echo "⚠️  Scheduler failed to start — Lexi API continues."
  echo "    Fix: Render → Environment → SERVICE_ACCOUNT_JSON_CONTENT (full Firebase JSON)"
  wait "$NODE_PID"
  exit $?
fi

# If either process exits later, restart the whole service
wait -n "$NODE_PID" "$PY_PID"
EXIT_CODE=$?
cleanup
exit "$EXIT_CODE"
