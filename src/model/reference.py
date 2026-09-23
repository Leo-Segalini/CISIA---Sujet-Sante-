"""Modèle de référence (baseline) : probabilité = prévalence train."""

from __future__ import annotations

import numpy as np
import pandas as pd


class PrevalenceReference:
    """Prédit la prévalence observée sur le train pour toutes les lignes."""

    def __init__(self) -> None:
        self.prevalence_: float = 0.5

    def fit(self, X: pd.DataFrame, y: pd.Series) -> PrevalenceReference:
        self.prevalence_ = float(pd.Series(y).mean())
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.prevalence_
        n = len(X)
        return np.column_stack([np.full(n, 1.0 - p), np.full(n, p)])
