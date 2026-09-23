from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.model.bias import bias_table
from src.model.deploy import train_score
from src.model.explain import shap_top_features
from src.model.inference import predict_proba, threshold_for
from src.model.prepare import by_split, split_xy


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    paths.ensure_data_dirs()
    use_optuna = "--optuna" in sys.argv
    mapping = {
        "score_sortie": paths.curated / "features_score_sortie.parquet",
        "score_tele": paths.curated / "features_score_tele.parquet",
    }
    for name, parquet in mapping.items():
        if not parquet.exists():
            raise FileNotFoundError(
                f"{parquet} absent — lancer d'abord PYTHONPATH=. python scripts/run_pipeline.py"
            )
        features = pd.read_parquet(parquet)
        report = train_score(
            features, score_name=name, paths=paths, use_optuna=use_optuna
        )
        bundle = joblib.load(paths.models / f"{name}_bundle.joblib")
        X, y, split = split_xy(features)
        X_te, y_te = by_split(X, y, split, "test")
        retenu = report["retenu"]
        proba = predict_proba(bundle, retenu, X_te)
        thr = threshold_for(report, retenu)
        pred = (proba >= thr).astype(int)
        bias = bias_table(X_te, y_te, pd.Series(pred, index=X_te.index))
        bias.to_csv(paths.models / f"{name}_biais.csv", index=False)
        if "coder" in bundle and "hgb" in bundle:
            shap_df = shap_top_features(bundle["coder"], bundle["hgb"], X)
            shap_df.to_csv(paths.models / f"{name}_shap.csv", index=False)
        print(
            json.dumps(
                {
                    "score": name,
                    "retenu": report["retenu"],
                    "ranking": report["ranking_test_pr_auc"],
                    "test_retenu": report[retenu]["test"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
