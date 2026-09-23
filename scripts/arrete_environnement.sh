#!/usr/bin/env bash
# Arrête Jupyter, webapp locale et conteneurs Docker CISIA.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

stop_pid() {
  local name="$1" file="$2"
  if [[ -f "$file" ]]; then
    local pid
    pid=$(cat "$file")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Arrêt $name (pid $pid)"
    fi
    rm -f "$file"
  fi
}

stop_pid "Jupyter" "$RUN_DIR/jupyter.pid"
stop_pid "Webapp locale" "$RUN_DIR/webapp.pid"

pkill -f "jupyter-notebook.*$ROOT/notebooks" 2>/dev/null || true
pkill -f "scripts/run_webapp.py" 2>/dev/null || true

if command -v docker >/dev/null 2>&1; then
  cd "$ROOT"
  docker compose down --remove-orphans 2>/dev/null || true
  for name in cisia-api cisia-retrain; do
    docker rm -f "$name" 2>/dev/null || true
  done
  echo "Docker compose arrêté"
fi

echo "Environnement CISIA arrêté."
