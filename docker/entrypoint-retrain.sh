#!/bin/sh
set -e
cd /app

INTERVAL="${RETRAIN_INTERVAL_SECONDS:-86400}"
OPTUNA="${RETRAIN_OPTUNA:-1}"
TRIALS="${OPTUNA_TRIALS:-25}"
API_URL="${WEBAPP_INTERNAL_URL:-http://webapp:8000}"
API_KEY="${ML_API_KEY:-}"

echo "=== CISIA retrain-worker — intervalle ${INTERVAL}s ==="

wait_for_api() {
  until wget -q -O- "${API_URL}/api/health" >/dev/null 2>&1; do
    echo "[retrain] En attente de l'API ${API_URL}…"
    sleep 5
  done
  echo "[retrain] API disponible."
}

trigger_retrain() {
  echo "[retrain] Lancement ré-entraînement $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$API_KEY" ]; then
    wget -q -O- \
      --header="Content-Type: application/json" \
      --header="X-ML-API-Key: ${API_KEY}" \
      --post-data="{\"optuna\": ${OPTUNA}, \"trials\": ${TRIALS}}" \
      "${API_URL}/api/ml/retrain" || echo "[retrain] Échec appel API"
  else
    PYTHONPATH=/app python scripts/run_retrain.py \
      $([ "$OPTUNA" = "1" ] && echo --optuna) \
      --trials "$TRIALS" || echo "[retrain] Échec script local"
  fi
}

wait_for_api
# Premier entraînement différé (bootstrap déjà fait au démarrage webapp)
sleep 60
trigger_retrain

while true; do
  sleep "$INTERVAL"
  trigger_retrain
done
