"""Calibration des probabilités (hôpital : proba ≈ fréquence réelle)."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.pipeline import Pipeline


def calibrate_prefit(
    model: Pipeline,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    *,
    method: str = "sigmoid",
) -> CalibratedClassifierCV:
    """Calibre un modèle déjà fit (train) sur le jeu de validation (sklearn ≥ 1.6)."""
    if y_val.nunique() < 2:
        raise ValueError("Validation sans les deux classes — calibration impossible")
    calibrated = CalibratedClassifierCV(
        estimator=FrozenEstimator(model),
        method=method,
        cv=2,
        ensemble=False,
    )
    calibrated.fit(X_val, y_val)
    return calibrated


def predict_calibrated(calibrated: Any, X: pd.DataFrame):
    return calibrated.predict_proba(X)[:, 1]
