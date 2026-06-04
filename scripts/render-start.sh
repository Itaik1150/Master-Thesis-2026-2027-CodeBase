#!/usr/bin/env bash
# Render start: Lexi API (foreground, keeps container alive) + Python scheduler (background).
# The scheduler is best-effort — if it can't start (e.g. missing Firebase creds),
# the Lexi API still runs so the app/admin keep working.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Starting proactive scheduler (logic-python) in background..."
(
  cd "$ROOT/logic-python"
  python scheduler.py || echo "⚠️  Scheduler stopped (see error above) — Lexi API keeps running."
) &

echo "==> Starting Lexi Node server (foreground)..."
cd "$ROOT/Lexi/server"
exec node build/server.js
