#!/usr/bin/env bash
# Installation complète + lancement CISIA (venv, deps, env, pipeline si besoin, services).
# Affiche en fin les liens Jupyter : sommaire + journal de bord.
#
# Usage :
#   ./scripts/install_et_lance.sh
#   ./scripts/install_et_lance.sh --webapp-locale
#   ./scripts/install_et_lance.sh --skip-pipeline
#   ./scripts/install_et_lance.sh --skip-docker
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WEBAPP_LOCALE=0
SKIP_PIPELINE=0
SKIP_DOCKER=0
LANCE_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --webapp-locale) WEBAPP_LOCALE=1; LANCE_ARGS+=(--webapp-locale); shift ;;
    --skip-pipeline) SKIP_PIPELINE=1; shift ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/install_et_lance.sh [options]

  1. Crée .venv si besoin
  2. pip install -r requirements.txt
  3. Copie .env.example → .env si absent
  4. Lance le pipeline features (si parquet absent)
  5. Démarre Jupyter + webapp (+ Docker sauf --skip-docker)

Options :
  --webapp-locale   Webapp locale avec LLM (comme lance_environnement.sh)
  --skip-pipeline   Ne pas lancer run_pipeline.py
  --skip-docker     Ne pas démarrer Docker (Jupyter + webapp locale seulement)

Arrêt : ./scripts/arrete_environnement.sh
EOF
      exit 0
      ;;
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
  esac
done

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }

# --- Python / venv ---
log "Installation — environnement Python"
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 introuvable." >&2
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  log "Création du virtualenv (.venv)"
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
ok "venv actif : $(python -V)"

log "Installation des dépendances (requirements.txt)"
python -m pip install -q --upgrade pip
python -m pip install -q -r "$ROOT/requirements.txt"
# Jupyter notebook UI
python -m pip install -q notebook 2>/dev/null || true
ok "Dépendances installées"

# --- .env ---
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn ".env créé depuis .env.example — personnalisez les secrets si besoin."
else
  ok ".env déjà présent"
fi

export PYTHONPATH="$ROOT"

# --- Pipeline features ---
FEAT="$ROOT/data/curated/features_score_sortie.parquet"
if [[ "$SKIP_PIPELINE" == "1" ]]; then
  warn "Pipeline ignoré (--skip-pipeline)"
elif [[ -f "$FEAT" ]]; then
  ok "Features déjà présentes : data/curated/"
else
  log "Pipeline données (features curated)…"
  PYTHONPATH="$ROOT" python "$ROOT/scripts/run_pipeline.py"
  ok "Pipeline terminé"
fi

# --- Lancement services ---
chmod +x "$ROOT/scripts/lance_environnement.sh" "$ROOT/scripts/arrete_environnement.sh" 2>/dev/null || true

if [[ "$SKIP_DOCKER" == "1" ]]; then
  log "Lancement Jupyter + webapp locale (sans Docker)"
  export WEBAPP_LOCALE=1
  # Jupyter seulement + webapp locale manuelle
  JUPYTER_PORT="${JUPYTER_PORT:-8888}"
  RUN_DIR="$ROOT/.run"
  mkdir -p "$RUN_DIR"
  if [[ -f "$RUN_DIR/jupyter.pid" ]]; then
    old="$(cat "$RUN_DIR/jupyter.pid" 2>/dev/null || true)"
    [[ -n "${old:-}" ]] && kill "$old" 2>/dev/null || true
    rm -f "$RUN_DIR/jupyter.pid"
  fi
  pkill -f "jupyter-notebook.*$ROOT/notebooks" 2>/dev/null || true
  sleep 1
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
  if ! pgrep -f "scripts/run_webapp.py" >/dev/null 2>&1; then
    export CISIA_LLM="${CISIA_LLM:-0}"
    nohup python "$ROOT/scripts/run_webapp.py" >"$RUN_DIR/webapp.log" 2>&1 &
    echo $! >"$RUN_DIR/webapp.pid"
  fi
  sleep 3
  WEB_URL="http://127.0.0.1:8000"
else
  log "Lancement environnement complet"
  CISIA_SKIP_BANNER=1 "$ROOT/scripts/lance_environnement.sh" "${LANCE_ARGS[@]+"${LANCE_ARGS[@]}"}"
  JUPYTER_PORT="${JUPYTER_PORT:-8888}"
  if [[ "$WEBAPP_LOCALE" == "1" ]]; then
    WEB_URL="http://127.0.0.1:8000"
  else
    WEB_URL="http://127.0.0.1:${WEBAPP_PORT:-8000}"
  fi
fi

JUPYTER_PORT="${JUPYTER_PORT:-8888}"
BASE="http://127.0.0.1:${JUPYTER_PORT}"
# URLs Notebook 7 (/doc/tree/…) — plus fiables que /notebooks/
TREE="${BASE}/tree"
JOURNAL="${BASE}/doc/tree/00_guide/02_journal_de_bord.ipynb"
SOMMAIRE="${BASE}/doc/tree/00_guide/00_sommaire.ipynb"
CADRE="${BASE}/doc/tree/00_guide/01_cadre_projet.ipynb"
INVENTAIRE="${BASE}/doc/tree/01_donnees/01_inventaire_sources.ipynb"

# Tentative d’ouverture navigateur (macOS)
if command -v open >/dev/null 2>&1; then
  open "$JOURNAL" 2>/dev/null || true
fi

PYTHON_VERSION="$(python -V 2>&1 || echo 'Python inconnu')"
PYTHON_PATH="$(command -v python 2>/dev/null || echo 'n/a')"

cat <<EOF

════════════════════════════════════════════════════════════════
  CISIA Santé — installé et démarré
════════════════════════════════════════════════════════════════

  Python utilisé : ${PYTHON_VERSION}
  Exécutable     : ${PYTHON_PATH}

  Ouvrir le cahier électronique (Jupyter)
  ----------------------------------------
  Arborescence notebooks :  ${TREE}

  ★ Journal de bord (méthode & choix) :
    ${JOURNAL}

  ★ Sommaire / parcours CIF :
    ${SOMMAIRE}

  Cadre projet :
    ${CADRE}

  Inventaire des données :
    ${INVENTAIRE}

  Application web (démo)
  ----------------------
  Hub      : ${WEB_URL}/
  CISIA    : ${WEB_URL}/cisia
  Analyse  : ${WEB_URL}/cisia/analyse
  Modèles  : ${WEB_URL}/cisia/modeles
  Soignant : ${WEB_URL}/soignant

  Arrêt : ./scripts/arrete_environnement.sh
════════════════════════════════════════════════════════════════
EOF
