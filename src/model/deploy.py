from __future__ import annotations

import json

import joblib
import pandas as pd

from src.data.paths import ProjectPaths
from src.model.benchmark import model_catalog, run_benchmark
from src.model.calibration import calibrate_prefit
from src.model.prepare import by_split, split_xy
from src.model.trainers import (
    train_hgb_sklearn,
    train_lightgbm,
    train_mlp,
    train_random_forest,
)


def train_score(
    features: pd.DataFrame,
    *,
    score_name: str,
    paths: ProjectPaths,
    use_optuna: bool = False,
    optuna_trials: int = 25,
) -> dict:
    """Entraîne les 5 modèles, sélectionne le gagnant (PR-AUC test) et déploie le bundle."""
    report = run_benchmark(
        features,
        score_name=score_name,
        paths=paths,
        parallel=True,
        use_optuna=use_optuna,
        optuna_trials=optuna_trials,
    )

    X, y, split = split_xy(features)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_va, y_va = by_split(X, y, split, "val")

    bundle: dict = {}
    catalog = {s.key: s for s in model_catalog()}
    tunable_trainers = {
        "random_forest": train_random_forest,
        "lightgbm": train_lightgbm,
        "mlp": train_mlp,
    }

    for key in report["modeles"]:
        if key in report.get("skipped", {}):
            continue
        spec = catalog[key]
        optuna_p = report["modeles"][key].get("optuna_params")
        if optuna_p and spec.tunable:
            artifact = tunable_trainers[key](X_tr, y_tr, params=optuna_p)
        else:
            artifact = spec.train(X_tr, y_tr)
        if artifact is not None:
            bundle[key] = artifact

    if "lightgbm" not in bundle:
        coder, hgb = train_hgb_sklearn(X_tr, y_tr)
        bundle["coder"] = coder
        bundle["hgb"] = hgb

    retenu = report["retenu"]
    bundle["retenu"] = retenu

    # Calibration hôpital du modèle retenu (proba sur validation)
    if retenu in bundle and hasattr(bundle[retenu], "predict_proba"):
        try:
            bundle["calibrated"] = calibrate_prefit(bundle[retenu], X_va, y_va)
            bundle["calibrated_method"] = "sigmoid_prefit_val"
        except ValueError:
            pass

    paths.ensure_data_dirs()
    joblib.dump(bundle, paths.models / f"{score_name}_bundle.joblib")

    metrics_out: dict = {
        "score": score_name,
        "n_train": report["n_train"],
        "n_val": report["n_val"],
        "n_test": report["n_test"],
        "retenu": retenu,
        "ranking_test_pr_auc": report["ranking_test_pr_auc"],
        "optuna": report.get("optuna", False),
        "calibrated": "calibrated" in bundle,
        "justification_algo": report.get("note", ""),
    }
    for key, data in report["modeles"].items():
        metrics_out[key] = {
            "modele": key,
            "label": data["label"],
            "val": data["val"],
            "test": data["test"],
        }
        if "optuna_params" in data:
            metrics_out[key]["optuna_params"] = data["optuna_params"]

    metrics_path = paths.models / f"{score_name}_metrics.json"
    metrics_path.write_text(
        json.dumps(metrics_out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return metrics_out
