#!/usr/bin/env python3
"""Ré-entraînement complet (données + modèles + registry)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.mlops.retrain import run_full_retrain


def main() -> None:
    parser = argparse.ArgumentParser(description="Ré-entraînement CISIA Santé")
    parser.add_argument("--optuna", action="store_true", help="Activer Optuna (RF, LightGBM, MLP)")
    parser.add_argument("--trials", type=int, default=25, help="Nombre d'essais Optuna")
    args = parser.parse_args()
    paths = ProjectPaths(root=get_project_root())
    result = run_full_retrain(
        paths,
        use_optuna=args.optuna,
        optuna_trials=args.trials,
        source="cli",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
