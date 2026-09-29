#!/usr/bin/env bash
# Arrête uniquement Jupyter (laisse Docker / webapp intacts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

if [[ -f "$RUN_DIR/jupyter.pid" ]]; then
  pid="$(cat "$RUN_DIR/jupyter.pid")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "Arrêt Jupyter (pid $pid)"
  fi
  rm -f "$RUN_DIR/jupyter.pid"
fi

pkill -f "jupyter-notebook.*$ROOT/notebooks" 2>/dev/null || true
echo "Jupyter arrêté."
