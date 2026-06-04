#!/usr/bin/env bash
# Render build: Lexi Node server + Python proactive scheduler deps
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building Lexi server..."
cd "$ROOT/Lexi/server"
npm install
npm run build

echo "==> Installing Python dependencies..."
cd "$ROOT/logic-python"
pip install -r requirements.txt

echo "==> Build complete."
