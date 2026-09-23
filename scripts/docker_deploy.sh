#!/bin/sh
set -e
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Créé .env depuis .env.example — éditez ML_API_KEY avant la prod."
fi

echo "=== Build image cisia-api ==="
docker build -t cisia-api:latest .

echo "=== Démarrage API + retrain-worker ==="
docker compose up -d

echo ""
echo "API : http://localhost:${WEBAPP_PORT:-8000}"
echo "Logs : docker compose logs -f"
echo "Santé : curl http://localhost:8000/api/health"
