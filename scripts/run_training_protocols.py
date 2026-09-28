#!/usr/bin/env python3
"""Compare hold-out vs CV patient vs CV stratifiée (logistic + random_forest)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data.paths import ProjectPaths, get_project_root
from src.model.cv_protocols import compare_training_protocols


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    paths.ensure_data_dirs()
    out_dir = paths.models / "protocoles"
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    mapping = {
        "score_sortie": paths.curated / "features_score_sortie.parquet",
        "score_tele": paths.curated / "features_score_tele.parquet",
    }
    for score_name, parquet in mapping.items():
        if not parquet.exists():
            raise FileNotFoundError(
                f"{parquet} absent — lancer PYTHONPATH=. python scripts/run_pipeline.py"
            )
        features = pd.read_parquet(parquet)
        print(f"▶ Protocoles sur {score_name} ({features.shape[0]} séjours)…")
        df = compare_training_protocols(features, score_name=score_name)
        frames.append(df)
        print(df.to_string(index=False))

    report = pd.concat(frames, ignore_index=True)
    csv_path = out_dir / "comparaison_protocoles.csv"
    json_path = out_dir / "comparaison_protocoles.json"
    report.to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(report.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ Écrit {csv_path}")
    print(f"✓ Écrit {json_path}")
    print(
        "\nPourquoi : le hold-out reste le protocole de déploiement ; "
        "les CV mesurent la stabilité du score selon le découpage."
    )


if __name__ == "__main__":
    main()
