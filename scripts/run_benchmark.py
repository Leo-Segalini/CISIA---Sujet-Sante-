#!/usr/bin/env python3
"""Benchmark multi-modèles (reference, logistic, RF, HistGB, LightGBM, MLP)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data.paths import ProjectPaths, get_project_root
from src.model.benchmark import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--optuna", action="store_true")
    parser.add_argument("--trials", type=int, default=25)
    args = parser.parse_args()

    paths = ProjectPaths(root=get_project_root())
    mapping = {
        "score_sortie": paths.curated / "features_score_sortie.parquet",
        "score_tele": paths.curated / "features_score_tele.parquet",
    }
    for name, parquet in mapping.items():
        if not parquet.exists():
            raise FileNotFoundError(
                f"{parquet} absent — lancer PYTHONPATH=. python scripts/run_pipeline.py"
            )
        features = pd.read_parquet(parquet)
        report = run_benchmark(
            features,
            score_name=name,
            paths=paths,
            use_optuna=args.optuna,
            optuna_trials=args.trials,
        )
        print(
            json.dumps(
                {
                    "score": name,
                    "retenu": report["retenu"],
                    "ranking": report["ranking_test_pr_auc"],
                    "skipped": report.get("skipped"),
                    "optuna": report.get("optuna"),
                    "paths": report.get("paths"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
