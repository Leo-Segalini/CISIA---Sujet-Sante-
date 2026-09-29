#!/usr/bin/env bash
# Démarre uniquement Jupyter (cahier électronique) — sans Docker, webapp ni pipeline.
#
# Usage :
#   ./scripts/lance_notebook.sh
#   ./scripts/lance_notebook.sh --open   # ouvre le journal dans le navigateur
#   ./scripts/arrete_notebook.sh        # arrêt Jupyter seul
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

JUPYTER_PORT="${JUPYTER_PORT:-8888}"
OPEN_BROWSER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --open) OPEN_BROWSER=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/lance_notebook.sh [--open]

  Démarre Jupyter Notebook sur le dossier notebooks/ (port 8888).
  Crée .venv et installe les deps automatiquement si besoin.
  Ne lance ni Docker ni webapp.

  --open   Ouvre le journal de bord dans le navigateur (macOS/Linux)

Arrêt : ./scripts/arrete_notebook.sh
EOF
      exit 0
      ;;
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
  esac
done

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }

# --- Python / venv (création automatique si absent) ---
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 introuvable (installez Python 3.13)." >&2
  exit 1
fi

NEED_PIP=0
if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  log "Création du virtualenv (.venv) avec $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
  NEED_PIP=1
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
ok "venv actif : $(python -V)"

if [[ "$NEED_PIP" == "1" ]] || ! command -v jupyter >/dev/null 2>&1; then
  log "Installation des dépendances (requirements.txt + notebook)"
  python -m pip install -q --upgrade pip
  if [[ -f "$ROOT/requirements.txt" ]]; then
    python -m pip install -q -r "$ROOT/requirements.txt"
  fi
  python -m pip install -q notebook
  ok "Dépendances installées"
fi

if ! command -v jupyter >/dev/null 2>&1; then
  echo "jupyter toujours introuvable après installation." >&2
  exit 1
fi

if [[ ! -f "$ROOT/.env" && -f "$ROOT/.env.example" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn ".env créé depuis .env.example"
fi

export PYTHONPATH="$ROOT"

# Redémarrage propre de Jupyter uniquement
if [[ -f "$RUN_DIR/jupyter.pid" ]]; then
  old="$(cat "$RUN_DIR/jupyter.pid" 2>/dev/null || true)"
  if [[ -n "${old:-}" ]] && kill -0 "$old" 2>/dev/null; then
    log "Arrêt de l’instance Jupyter précédente (pid $old)"
    kill "$old" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$RUN_DIR/jupyter.pid"
fi
pkill -f "jupyter-notebook.*$ROOT/notebooks" 2>/dev/null || true
# Libère le port si un orphelin l’occupe
if lsof -nP -iTCP:"$JUPYTER_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  warn "Port $JUPYTER_PORT occupé — libération"
  lsof -nP -iTCP:"$JUPYTER_PORT" -sTCP:LISTEN -t 2>/dev/null | while read -r pid; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
fi

log "Démarrage Jupyter (port $JUPYTER_PORT)"
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

BASE="http://127.0.0.1:${JUPYTER_PORT}"
TREE="${BASE}/tree"
# Notebook 7 : /doc/tree/... ouvre l’éditeur (évite les 404 / erreurs « Server Error » du vieux chemin)
JOURNAL="${BASE}/doc/tree/00_guide/02_journal_de_bord.ipynb"
SOMMAIRE="${BASE}/doc/tree/00_guide/00_sommaire.ipynb"
CADRE="${BASE}/doc/tree/00_guide/01_cadre_projet.ipynb"

JUPYTER_OK=0
for i in $(seq 1 30); do
  if curl -sf "$TREE" >/dev/null 2>&1 \
    && curl -sf "${BASE}/api/contents/00_guide/02_journal_de_bord.ipynb" >/dev/null 2>&1; then
    JUPYTER_OK=1
    break
  fi
  sleep 1
done

if [[ "$JUPYTER_OK" == "1" ]]; then
  ok "Jupyter prêt"
else
  warn "Jupyter ne répond pas — voir .run/jupyter.log"
  if [[ -f "$RUN_DIR/jupyter.log" ]]; then
    tail -n 25 "$RUN_DIR/jupyter.log" || true
  fi
  exit 1
fi

open_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" 2>/dev/null || true
  fi
}

# Ouvre le journal une fois le serveur vraiment prêt (--open ou par défaut sur macOS)
if [[ "$OPEN_BROWSER" == "1" ]] || [[ "$(uname -s)" == "Darwin" ]]; then
  open_url "$JOURNAL"
fi

PYTHON_VERSION="$(python -V 2>&1 || echo 'Python inconnu')"
PYTHON_PATH="$(command -v python 2>/dev/null || echo 'n/a')"

cat <<EOF

════════════════════════════════════════════════════════════════
  CISIA Santé — Jupyter seul (cahier électronique)
════════════════════════════════════════════════════════════════

  Python utilisé : ${PYTHON_VERSION}
  Exécutable     : ${PYTHON_PATH}

  Arborescence notebooks :
    ${TREE}

  ★ Journal de bord (méthode & choix) :
    ${JOURNAL}

  ★ Sommaire / parcours CIF :
    ${SOMMAIRE}

  Cadre projet :
    ${CADRE}

  Arrêt : ./scripts/arrete_notebook.sh
════════════════════════════════════════════════════════════════
EOF
