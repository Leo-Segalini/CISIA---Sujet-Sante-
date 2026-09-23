from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(y_true, proba, threshold: float) -> dict[str, float]:
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    pred = (proba >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, pred, beta=2, zero_division=0)),
        "threshold": float(threshold),
        "n": int(len(y_true)),
        "prevalence": float(y_true.mean()),
    }


def best_f2_threshold(y_true, proba, *, grid: int = 37) -> float:
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    thresholds = np.linspace(0.05, 0.95, grid)
    best_t = 0.5
    best_s = -1.0
    for t in thresholds:
        pred = (proba >= t).astype(int)
        s = float(fbeta_score(y_true, pred, beta=2, zero_division=0))
        if s > best_s:
            best_s = s
            best_t = float(t)
    return best_t
