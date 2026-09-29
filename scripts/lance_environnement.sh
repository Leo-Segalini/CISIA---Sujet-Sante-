#!/usr/bin/env bash
# Lance Docker (API + ré-entraînement), Jupyter et la webapp CISIA.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

WEBAPP_PORT="${WEBAPP_PORT:-8000}"
JUPYTER_PORT="${JUPYTER_PORT:-8888}"
WEBAPP_LOCALE="${WEBAPP_LOCALE:-0}"

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }

# Arrête compose + supprime les conteneurs orphelins au nom fixe (conflit fréquent).
docker_cisia_reset() {
  docker compose down --remove-orphans 2>/dev/null || true
  for name in cisia-api cisia-retrain; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      warn "Conteneur orphelin détecté : $name — suppression"
      docker rm -f "$name" >/dev/null 2>&1 || true
    fi
  done
}

docker_cisia_up() {
  local port="$1"
  docker_cisia_reset
  docker build -t cisia-api:latest "$ROOT"
  # Ne fait pas échouer tout le script si le healthcheck Compose est trop strict :
  # on attend ensuite /api/health nous-mêmes.
  set +e
  WEBAPP_PORT="$port" docker compose up -d
  local rc=$?
  set -e
  return "$rc"
}

# --- Options ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --webapp-locale) WEBAPP_LOCALE=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/lance_environnement.sh [--webapp-locale]

  Docker API + retrain-worker (port 8000 par défaut)
  Jupyter Notebook (port 8888)
  Webapp : via Docker (défaut) ou locale avec LLM (--webapp-locale)

Arrêt : ./scripts/arrete_environnement.sh
EOF
      exit 0
      ;;
    *) warn "Option inconnue : $1"; shift ;;
  esac
done

# --- Environnement Python ---
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
else
  warn "Pas de .venv — utilisez : python3.13 -m venv .venv && pip install -r requirements.txt"
fi

export PYTHONPATH="$ROOT"

# --- .env Docker ---
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn ".env créé depuis .env.example — pensez à définir ML_API_KEY."
fi

# --- 1. Docker ---
log "1/3 — Docker (API + ré-entraînement)"
if ! command -v docker >/dev/null 2>&1; then
  warn "Docker absent — étape ignorée."
else
  if [[ "$WEBAPP_LOCALE" == "1" ]]; then
    warn "Mode webapp locale (LLM) : Docker API sur le port 8001, webapp locale sur 8000."
    docker_cisia_up 8001
    ok "Conteneurs démarrés (API MLOps :8001)"
    log "Attente santé API Docker…"
    for i in $(seq 1 60); do
      if curl -sf "http://127.0.0.1:8001/api/health" >/dev/null 2>&1; then
        ok "API Docker (MLOps) healthy sur :8001"
        break
      fi
      sleep 2
      [[ "$i" == "60" ]] && warn "API Docker non joignable — docker compose logs webapp"
    done
  else
    if lsof -i ":$WEBAPP_PORT" -sTCP:LISTEN 2>/dev/null | grep -qv docker; then
      warn "Port $WEBAPP_PORT déjà utilisé (webapp locale ?). Arrêtez-la ou utilisez --webapp-locale."
    fi
    if ! docker_cisia_up "$WEBAPP_PORT"; then
      warn "Docker Compose n’est pas devenu healthy — bascule webapp locale (sans Docker)."
      WEBAPP_LOCALE=1
      docker_cisia_reset
    else
      ok "Conteneurs démarrés (cisia-api, cisia-retrain)"
      log "Attente santé API…"
      API_OK=0
      for i in $(seq 1 90); do
        if curl -sf "http://127.0.0.1:$WEBAPP_PORT/api/health" >/dev/null 2>&1; then
          ok "API Docker healthy"
          API_OK=1
          break
        fi
        sleep 2
      done
      if [[ "$API_OK" != "1" ]]; then
        warn "API Docker non joignable — bascule webapp locale. Logs : docker compose logs webapp"
        WEBAPP_LOCALE=1
        docker_cisia_reset
      fi
    fi
  fi
fi

# --- 2. Jupyter ---
log "2/3 — Jupyter Notebook"

# Arrête une instance précédente (évite le basculement silencieux 8888 → 8889).
if [[ -f "$RUN_DIR/jupyter.pid" ]]; then
  old_pid="$(cat "$RUN_DIR/jupyter.pid" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    warn "Arrêt Jupyter précédent (pid $old_pid)"
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$RUN_DIR/jupyter.pid"
fi
# Tue aussi les orphelins sur le port cible
if lsof -nP -iTCP:"$JUPYTER_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  warn "Port $JUPYTER_PORT occupé — libération"
  lsof -nP -iTCP:"$JUPYTER_PORT" -sTCP:LISTEN -t 2>/dev/null | while read -r pid; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
fi
# Orphelins jupyter-notebook du projet
pkill -f "jupyter-notebook.*$ROOT/notebooks" 2>/dev/null || true
sleep 1

if ! command -v jupyter >/dev/null 2>&1; then
  warn "jupyter absent du PATH — pip install notebook dans le .venv"
else
  nohup jupyter notebook "$ROOT/notebooks" \
    --no-browser \
    --port="$JUPYTER_PORT" \
    --ip=127.0.0.1 \
    --ServerApp.port_retries=0 \
    --ServerApp.token='' \
    --ServerApp.password='' \
    --IdentityProvider.token='' \
    >"$RUN_DIR/jupyter.log" 2>&1 &
  echo $! >"$RUN_DIR/jupyter.pid"
  sleep 3
  if curl -sf "http://127.0.0.1:$JUPYTER_PORT/tree" >/dev/null 2>&1; then
    ok "Jupyter : http://127.0.0.1:$JUPYTER_PORT/tree"
  else
    warn "Jupyter ne répond pas sur :$JUPYTER_PORT — voir .run/jupyter.log"
    if [[ -f "$RUN_DIR/jupyter.log" ]]; then
      tail -n 20 "$RUN_DIR/jupyter.log" || true
    fi
  fi
fi

# --- 3. Webapp ---
log "3/3 — Webapp CISIA"
if [[ "$WEBAPP_LOCALE" == "1" ]]; then
  if pgrep -f "scripts/run_webapp.py" >/dev/null 2>&1; then
    ok "Webapp locale déjà active"
  else
    export CISIA_LLM="${CISIA_LLM:-1}"
    nohup python "$ROOT/scripts/run_webapp.py" >"$RUN_DIR/webapp.log" 2>&1 &
    echo $! >"$RUN_DIR/webapp.pid"
    sleep 3
    ok "Webapp locale (LLM) : http://127.0.0.1:8000 (logs : .run/webapp.log)"
  fi
else
  ok "Webapp Docker : http://127.0.0.1:$WEBAPP_PORT"
  ok "  Hub      → /"
  ok "  CISIA    → /cisia"
  ok "  Soignant → /soignant"
fi

# --- Récap (sautable si appelé depuis install_et_lance.sh) ---
if [[ "$WEBAPP_LOCALE" == "1" ]]; then
  WEB_URL="http://127.0.0.1:8000"
  API_URL="http://127.0.0.1:8001"
else
  WEB_URL="http://127.0.0.1:$WEBAPP_PORT"
  API_URL="$WEB_URL"
fi

if [[ "${CISIA_SKIP_BANNER:-0}" == "1" ]]; then
  exit 0
fi

PYTHON_VERSION="$(python -V 2>&1 || echo 'Python inconnu')"
PYTHON_PATH="$(command -v python 2>/dev/null || echo 'n/a')"

cat <<EOF

════════════════════════════════════════════════════════════════
  CISIA Santé — environnement démarré
════════════════════════════════════════════════════════════════

  Python utilisé : $PYTHON_VERSION
  Exécutable     : $PYTHON_PATH

  Jupyter (arborescence) :
    http://127.0.0.1:$JUPYTER_PORT/tree

  ★ Journal de bord (méthode & choix) :
    http://127.0.0.1:$JUPYTER_PORT/doc/tree/00_guide/02_journal_de_bord.ipynb

  ★ Sommaire / parcours CIF :
    http://127.0.0.1:$JUPYTER_PORT/doc/tree/00_guide/00_sommaire.ipynb

  Cadre projet :
    http://127.0.0.1:$JUPYTER_PORT/doc/tree/00_guide/01_cadre_projet.ipynb

  Inventaire données :
    http://127.0.0.1:$JUPYTER_PORT/doc/tree/01_donnees/01_inventaire_sources.ipynb

  Webapp     : $WEB_URL
  API santé  : $API_URL/api/health
  MLOps      : $API_URL/api/ml/status

  Arrêt      : ./scripts/arrete_environnement.sh
════════════════════════════════════════════════════════════════
EOF
