#!/usr/bin/env python3
"""Bootstrap Docker : pipeline + modèles si absents."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.data.pipeline import run_pipeline
from src.model.deploy import train_score


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    paths.ensure_data_dirs()

    sortie_p = paths.curated / "features_score_sortie.parquet"
    if not sortie_p.exists():
        print("[bootstrap] Pipeline données…")
        run_pipeline(paths, horizon_tele=7)
    else:
        print("[bootstrap] Features curated OK")

    use_optuna = os.environ.get("RETRAIN_OPTUNA", "1") == "1"
    trials = int(os.environ.get("OPTUNA_TRIALS", "25"))

    import pandas as pd

    for score in ("score_sortie", "score_tele"):
        bundle = paths.models / f"{score}_bundle.joblib"
        parquet = paths.curated / f"features_{score}.parquet"
        if bundle.exists():
            print(f"[bootstrap] {score} bundle OK")
            continue
        if not parquet.exists():
            raise FileNotFoundError(f"{parquet} manquant")
        print(f"[bootstrap] Entraînement {score} (optuna={use_optuna})…")
        features = pd.read_parquet(parquet)
        report = train_score(
            features,
            score_name=score,
            paths=paths,
            use_optuna=use_optuna,
            optuna_trials=trials,
        )
        print(f"[bootstrap] {score} retenu : {report['retenu']}")

    print("[bootstrap] Terminé.")


if __name__ == "__main__":
    main()
