"""Inférence unifiée sur le bundle de modèles."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.model.reference import PrevalenceReference
from src.model.train import CategoryToCode, predict_hgb, predict_logistic
from src.model.trainers import predict_pipeline, predict_reference


def predict_proba(
    bundle: dict[str, Any],
    modele: str,
    X: pd.DataFrame,
) -> np.ndarray:
    # Production hôpital : proba calibrée si le modèle demandé est le retenu
    if (
        bundle.get("calibrated") is not None
        and modele == bundle.get("retenu")
        and not isinstance(bundle.get("calibrated"), bool)
    ):
        return np.asarray(bundle["calibrated"].predict_proba(X)[:, 1])
    if modele == "reference":
        return predict_reference(bundle["reference"], X)
    if modele == "logistic":
        return predict_logistic(bundle["logistic"], X)
    if modele == "hgb":
        coder: CategoryToCode = bundle["coder"]
        return predict_hgb(coder, bundle["hgb"], X)
    if modele in {"random_forest", "lightgbm", "mlp"}:
        model: Pipeline = bundle[modele]
        return predict_pipeline(model, X)
    raise KeyError(f"Modèle inconnu dans le bundle : {modele}")


def threshold_for(metrics: dict, modele: str) -> float:
    if modele in metrics and isinstance(metrics[modele], dict):
        return float(metrics[modele]["test"]["threshold"])
    if modele == "hgb" and "lightgbm" in metrics:
        return float(metrics["lightgbm"]["test"]["threshold"])
    return float(metrics.get("logistic", {}).get("test", {}).get("threshold", 0.35))


def score_single(
    bundle: dict[str, Any],
    metrics: dict,
    X: pd.DataFrame,
    *,
    modele: str | None = None,
) -> dict[str, Any]:
    retenu = modele or metrics.get("retenu", "logistic")
    proba = float(predict_proba(bundle, retenu, X)[0])
    thr = threshold_for(metrics, retenu)
    return {
        "proba": proba,
        "seuil": thr,
        "alerte": proba >= thr,
        "modele": retenu,
    }
