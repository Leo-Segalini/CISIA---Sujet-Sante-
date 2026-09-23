#!/bin/sh
set -e
cd /app
echo "=== CISIA API — démarrage ==="
python scripts/docker_bootstrap.py
exec uvicorn src.web.app:app \
  --host "${WEBAPP_HOST:-0.0.0.0}" \
  --port "${WEBAPP_PORT:-8000}"
