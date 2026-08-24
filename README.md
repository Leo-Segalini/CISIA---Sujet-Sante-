# CISIA Santé — Prédiction du risque de réadmission à 30 jours

Données **synthétiques** uniquement : jamais une décision clinique réelle.

## Chantier actuel : fondation données

Pipeline local (aucun appel réseau) : inventaire, coffre identité, qualité, registre de sensibilité, deux scores (sortie / télésurveillance), exports `data/curated/` **hors git**.

- Spec : `docs/superpowers/specs/2026-08-24-fondation-donnees-readmission-design.md`
- Plan : `docs/superpowers/plans/2026-08-24-fondation-donnees-readmission.md`

## Environnement

Python **3.13** (les roues `pyarrow` ne sont pas disponibles pour 3.14 sur cette machine).

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -v
PYTHONPATH=. python scripts/run_pipeline.py
```

Les CSV du sujet restent à la racine. Copies de travail (`data/raw`, coffre, curated) sont ignorées par git.
