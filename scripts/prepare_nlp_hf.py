#!/usr/bin/env python3
"""
Fine-tuning NLP optionnel sur Hugging Face (CR masqués uniquement).

Prérequis :
  - export HF_TOKEN=...   # ne jamais committer la clé
  - données masquées via src/nlp/masking.py
  - GPU recommandé pour un vrai fine-tune

Ce script prépare le jeu d'entraînement masqué et documente la commande TRL.
L'entraînement cloud HF n'est pas lancé automatiquement (coût + conformité).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data.identity import split_identity_and_pseudonymise
from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root
from src.nlp.masking import documents_par_sejour, mask_comptes_rendus


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    patients = load_csv(paths, "patients.csv", from_raw=False)
    vault, _ = split_identity_and_pseudonymise(patients)
    sejours = load_csv(paths, "sejours.csv", from_raw=False)
    cr = load_csv(paths, "comptes_rendus.csv", from_raw=False)
    masked = mask_comptes_rendus(cr, vault, sejours)
    docs = documents_par_sejour(masked)
    feats = paths.curated / "features_score_sortie.parquet"
    if not feats.exists():
        raise FileNotFoundError("Lancer scripts/run_pipeline.py d'abord")
    features = pd.read_parquet(feats)
    dataset = docs.merge(features[["SejourID", "Readmission30j"]], on="SejourID")
    out = paths.models / "nlp_hf_dataset_masque.parquet"
    paths.ensure_data_dirs()
    dataset.to_parquet(out, index=False)

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    summary = {
        "dataset": str(out),
        "n_lignes": int(len(dataset)),
        "colonnes": list(dataset.columns),
        "hf_token_present": bool(hf_token),
        "etapes_suggerees": [
            "Choisir un petit modèle instruct (ex. Qwen2.5-1.5B) sur le Hub",
            "Fine-tuner avec TRL SFT sur la colonne document (texte masqué)",
            "Exporter en GGUF pour inference locale llama.cpp",
            "Ne jamais envoyer le vault identité ni les CSV bruts au cloud",
        ],
        "note": "Le score tabulaire reste entièrement local (benchmark sklearn/xgboost).",
    }
    report_path = paths.models / "nlp_hf_prepare.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
