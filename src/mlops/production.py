"""Contrat production hôpital : modèles figés, manifeste, promotion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import joblib
import pandas as pd

from src.data.paths import ProjectPaths
from src.mlops.monitoring import build_monitoring_snapshot, write_monitoring_baseline
from src.mlops.registry import register_version
from src.model.calibration import calibrate_prefit
from src.model.metrics import best_f2_threshold, classification_metrics
from src.model.prepare import by_split, split_xy
from src.model.train import train_logistic
from src.model.trainers import train_random_forest

# Modèles officiels retenus pour la production (benchmark Optuna + stabilité CV).
PRODUCTION_MODELS: dict[str, str] = {
    "score_sortie": "random_forest",
    "score_tele": "logistic",
}


def _train_locked(model_key: str, X_tr: pd.DataFrame, y_tr: pd.Series):
    if model_key == "random_forest":
        return train_random_forest(X_tr, y_tr)
    if model_key == "logistic":
        return train_logistic(X_tr, y_tr)
    raise ValueError(f"Modèle prod non supporté: {model_key}")


def promote_score_to_production(
    features: pd.DataFrame,
    *,
    score_name: str,
    paths: ProjectPaths,
    source: str = "promote_production",
) -> dict[str, Any]:
    """Entraîne le modèle figé, calibre sur val, archive registry + métriques."""
    if score_name not in PRODUCTION_MODELS:
        raise KeyError(score_name)
    model_key = PRODUCTION_MODELS[score_name]

    X, y, split = split_xy(features)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_va, y_va = by_split(X, y, split, "val")
    X_te, y_te = by_split(X, y, split, "test")

    raw_model = _train_locked(model_key, X_tr, y_tr)
    calibrated = calibrate_prefit(raw_model, X_va, y_va)

    bundle: dict[str, Any] = {
        model_key: raw_model,
        "calibrated": calibrated,
        "retenu": model_key,
        "production": True,
        "calibrated_method": "sigmoid_prefit_val",
    }

    # Probas calibrées pour seuil F2 (val) et métriques test
    p_va = calibrated.predict_proba(X_va)[:, 1]
    p_te = calibrated.predict_proba(X_te)[:, 1]
    thr = best_f2_threshold(y_va, p_va)
    test_metrics = classification_metrics(y_te, p_te, thr)
    val_metrics = classification_metrics(y_va, p_va, thr)

    paths.ensure_data_dirs()
    joblib.dump(bundle, paths.models / f"{score_name}_bundle.joblib")

    metrics_out: dict[str, Any] = {
        "score": score_name,
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_va)),
        "n_test": int(len(X_te)),
        "retenu": model_key,
        "production": True,
        "calibrated": True,
        "calibrated_method": "sigmoid_prefit_val",
        "ranking_test_pr_auc": [model_key],
        "justification_algo": (
            f"Production hôpital : {model_key} figé, hold-out patient, "
            "calibration sigmoid sur validation, seuil F2 val."
        ),
        model_key: {
            "modele": model_key,
            "label": model_key,
            "val": val_metrics,
            "test": test_metrics,
        },
    }
    (paths.models / f"{score_name}_metrics.json").write_text(
        json.dumps(metrics_out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    version = register_version(
        paths, score_name=score_name, metrics=metrics_out, source=source
    )
    baseline = write_monitoring_baseline(paths, score_name, features, metrics_out)
    return {
        "score": score_name,
        "retenu": model_key,
        "test": test_metrics,
        "version": version,
        "monitoring_baseline": baseline,
    }


def write_production_manifest(
    paths: ProjectPaths, promotions: list[dict[str, Any]]
) -> Path:
    manifest = {
        "environment": "hopital_production",
        "protocol": "holdout_patient_calibrated",
        "created_at": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "models": PRODUCTION_MODELS,
        "scores": {
            p["score"]: {
                "retenu": p["retenu"],
                "version_id": p["version"].get("version_id"),
                "test_pr_auc": p["test"].get("pr_auc"),
                "test_f2": p["test"].get("f2"),
                "threshold": p["test"].get("threshold"),
                "calibrated": True,
            }
            for p in promotions
        },
        "surveillance": "src.mlops.monitoring + /api/ml/status + model_watch",
        "disclaimer": (
            "Aide à la décision uniquement — ne remplace pas l'avis clinique. "
            "Données synthétiques CISIA."
        ),
    }
    path = paths.models / "production_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_production_manifest(paths: ProjectPaths) -> dict[str, Any] | None:
    path = paths.models / "production_manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def promote_all_to_production(paths: ProjectPaths, *, source: str = "promote_production") -> dict:
    promotions = []
    for score_name in PRODUCTION_MODELS:
        parquet = paths.curated / f"features_{score_name}.parquet"
        if not parquet.exists():
            raise FileNotFoundError(f"Manquant: {parquet}")
        features = pd.read_parquet(parquet)
        promotions.append(
            promote_score_to_production(
                features, score_name=score_name, paths=paths, source=source
            )
        )
    manifest_path = write_production_manifest(paths, promotions)
    snap = build_monitoring_snapshot(paths)
    return {
        "promotions": promotions,
        "manifest": str(manifest_path),
        "monitoring": snap,
    }
