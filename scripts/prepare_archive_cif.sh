#!/usr/bin/env bash
# Archive ZIP de rendu CIF — contenu minimal (cahier + code + données + PPT jury).
# Exclut PDF/DOCX, notes orales, livrables personnels hors PPT, secrets, lourds.
# Usage : ./scripts/prepare_archive_cif.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%d)"
OUT_DIR="${ROOT}/dist"
ARCHIVE_NAME="CISIA_Sante_CIF_SegaliniBriant_${STAMP}.zip"
ARCHIVE_PATH="${OUT_DIR}/${ARCHIVE_NAME}"
STAGE="${OUT_DIR}/stage_cif"
DEST="${STAGE}/CISIA_Sante"

mkdir -p "$OUT_DIR"
rm -rf "$STAGE"
mkdir -p "$DEST"

echo "==> Assemblage minimal rendu CIF (liste blanche)…"

copy_path() {
  local src="$1"
  local dst_rel="${2:-$1}"
  if [[ ! -e "$ROOT/$src" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$DEST/$dst_rel")"
  if [[ -d "$ROOT/$src" ]]; then
    mkdir -p "$DEST/$dst_rel"
    rsync -a \
      --exclude '__pycache__/' \
      --exclude '.ipynb_checkpoints/' \
      --exclude '_archive/' \
      --exclude '*.pyc' \
      "$ROOT/$src/" "$DEST/$dst_rel/"
  else
    cp -a "$ROOT/$src" "$DEST/$dst_rel"
  fi
}

# --- Cahier électronique ---
copy_path "notebooks"

# --- Code reproductible ---
copy_path "src"
copy_path "tests"
copy_path "webapp"
copy_path "docs/registres"

# Documentation technique (pas les notes orales)
copy_path "documentation"

# --- Scripts utiles au jury (pas les outils perso / GGUF) ---
mkdir -p "$DEST/scripts"
for s in \
  prepare_archive_cif.sh \
  install_et_lance.sh \
  lance_environnement.sh \
  lance_notebook.sh \
  arrete_environnement.sh \
  arrete_notebook.sh \
  run_pipeline.py \
  run_benchmark.py \
  run_quality_report.py \
  run_training_protocols.py \
  train_models.py \
  promote_production.py \
  generate_registre_skeleton.py \
  run_webapp.py \
  docker_deploy.sh \
  docker_bootstrap.py
do
  copy_path "scripts/$s"
done
chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true

# --- Config / dépendances ---
for f in \
  README.md \
  Sujet.md \
  requirements.txt \
  pytest.ini \
  .env.example \
  .gitignore \
  Dockerfile \
  docker-compose.yml \
  .dockerignore \
  Projet_CISIA_LSB.pptx
do
  copy_path "$f"
done
copy_path "docker"

# --- Données sources synthétiques immuables (`donnees/`) ---
mkdir -p "$DEST/donnees"
for f in "$ROOT"/donnees/*.csv; do
  [[ -f "$f" ]] || continue
  cp -a "$f" "$DEST/donnees/$(basename "$f")"
done

# --- Métriques modèles légères (pas joblib / gguf / registry lourd) ---
mkdir -p "$DEST/models"
for f in \
  score_sortie_metrics.json \
  score_tele_metrics.json \
  production_manifest.json
do
  [[ -f "$ROOT/models/$f" ]] && cp -a "$ROOT/models/$f" "$DEST/models/$f"
done
if [[ -d "$ROOT/models/monitoring" ]]; then
  copy_path "models/monitoring"
fi
if [[ -d "$ROOT/models/protocoles" ]]; then
  copy_path "models/protocoles"
fi

# Emplacement data (vide + .gitkeep si besoin) — pipeline régénère curated
mkdir -p "$DEST/data"
printf '%s\n' \
  "# Dossiers dérivés absents volontairement (raw/curated/vault)." \
  "# Régénérer : PYTHONPATH=. python scripts/run_pipeline.py" \
  > "$DEST/data/README.md"

# Garanties : jamais de secrets / perso (sauf PPT jury autorisé)
rm -f "$DEST/.env"
find "$DEST" -iname '*.pdf' -delete
find "$DEST" -iname '*.docx' -delete
find "$DEST" -iname '*NOTES_ORALES*' -delete
find "$DEST" -iname '*Segalini*' ! -iname 'Projet_CISIA_LSB.pptx' -delete
find "$DEST" -iname '*SEGALINI*' ! -iname 'Projet_CISIA_LSB.pptx' -delete
# Autres PPTX éventuels, mais on conserve le livrable jury
find "$DEST" -iname '*.pptx' ! -name 'Projet_CISIA_LSB.pptx' -delete
find "$DEST" -iname 'Projet_CISIA*' ! -name 'Projet_CISIA_LSB.pptx' -delete
find "$DEST" -name '.DS_Store' -delete

# Ré-assurance : PPT jury présent à la racine de l’archive
if [[ -f "$ROOT/Projet_CISIA_LSB.pptx" ]]; then
  cp -a "$ROOT/Projet_CISIA_LSB.pptx" "$DEST/Projet_CISIA_LSB.pptx"
else
  echo "ATTENTION : Projet_CISIA_LSB.pptx introuvable à la racine du dépôt." >&2
fi

# Lire-moi de rendu
cat > "$DEST/LIRE_MOI_RENDU_CIF.md" << 'EOF'
# Archive de rendu CIF — CISIA Santé

**Candidat :** Léo Segalini Briant  
**Sujet :** prédiction du risque de réadmission à 30 jours (données synthétiques)

Cette archive contient **uniquement** le nécessaire au cahier électronique :

| Livrable | Emplacement |
|----------|-------------|
| Journal de bord (méthode & choix) | `notebooks/00_guide/02_journal_de_bord.ipynb` |
| Sommaire / parcours | `notebooks/00_guide/00_sommaire.ipynb` |
| Production écrite | `notebooks/01_donnees/` puis `notebooks/02_modeles/` |
| Code + tests | `src/`, `tests/` |
| Jeux de données CSV | `donnees/*.csv` (**ne pas modifier**) |
| Données de travail | `data/raw/` (copie) → `data/curated/` |
| Sujet (texte) | `Sujet.md` |
| Présentation jury | `Projet_CISIA_LSB.pptx` |

**Absents volontairement :** PDF/DOCX personnels, notes orales, autres PowerPoint, `.env`, `.venv`, modèles GGUF / `.joblib`, données dérivées `data/curated/`.

## Démarrage

```bash
cd CISIA_Sante
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
PYTHONPATH=. python scripts/run_pipeline.py
jupyter notebook notebooks/ --ip=127.0.0.1 --port=8888
```

Ordre : **journal de bord** → cadre → inventaire → analyse/qualité → nettoyage → préparation → entraînement → lancement → réponse.
EOF

# Nettoyage documentation personnelle éventuelle
rm -f "$DEST/documentation"/NOTES* 2>/dev/null || true

rm -f "$ARCHIVE_PATH"
(
  cd "$STAGE"
  zip -r -q "$ARCHIVE_PATH" CISIA_Sante
)

# Aperçu contenu
echo "==> Aperçu racine archive :"
unzip -l "$ARCHIVE_PATH" | awk '{print $4}' | grep -E '^CISIA_Sante/[^/]+$' | sort

rm -rf "$STAGE"

BYTES="$(wc -c < "$ARCHIVE_PATH" | tr -d ' ')"
echo ""
echo "==> Archive prête :"
echo "    $ARCHIVE_PATH"
echo "    Taille : ${BYTES} octets"
echo ""
echo "À remettre : ce ZIP uniquement."
