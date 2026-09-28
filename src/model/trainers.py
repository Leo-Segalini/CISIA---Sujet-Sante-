"""Entraîneurs des modèles du benchmark CISIA."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.model.preprocess import build_preprocessor
from src.model.reference import PrevalenceReference
from src.model.train import CategoryToCode, predict_hgb, train_hgb, train_logistic


class HistGradientBoostingArtifact:
    """Wrapper predict_proba pour le HGB (coder + classifieur)."""

    def __init__(self, coder: CategoryToCode, clf: Any):
        self.coder = coder
        self.clf = clf

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        proba_pos = predict_hgb(self.coder, self.clf, X)
        # Compatibilité sklearn : matrice (n, 2)
        return np.column_stack([1.0 - proba_pos, proba_pos])


def train_reference(X_train: pd.DataFrame, y_train: pd.Series) -> PrevalenceReference:
    return PrevalenceReference().fit(X_train, y_train)


def predict_reference(model: PrevalenceReference, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def train_hist_gradient_boosting(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    params: dict[str, Any] | None = None,
) -> HistGradientBoostingArtifact:
    coder, clf = train_hgb(X_train, y_train, params=params)
    return HistGradientBoostingArtifact(coder, clf)


def predict_hist_gradient_boosting(
    model: HistGradientBoostingArtifact, X: pd.DataFrame
) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def train_random_forest(
    X_train: pd.DataFrame, y_train: pd.Series, *, params: dict[str, Any] | None = None
) -> Pipeline:
    p = {
        "n_estimators": 200,
        "max_depth": 8,
        "min_samples_leaf": 12,
        "class_weight": "balanced_subsample",
        "random_state": 42,
        "n_jobs": -1,
    }
    if params:
        p.update(params)
    pre = build_preprocessor(X_train)
    clf = RandomForestClassifier(**p)
    pipe = Pipeline([("pre", pre), ("clf", clf)])
    pipe.fit(X_train, y_train)
    return pipe


def train_lightgbm(
    X_train: pd.DataFrame, y_train: pd.Series, *, params: dict[str, Any] | None = None
) -> Pipeline | None:
    try:
        import lightgbm as lgb
    except ImportError:
        return None
    p = {
        "n_estimators": 180,
        "max_depth": 4,
        "learning_rate": 0.06,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 1.5,
        "class_weight": "balanced",
        "random_state": 42,
        "n_jobs": -1,
        "verbose": -1,
    }
    if params:
        p.update(params)
    pre = build_preprocessor(X_train)
    clf = lgb.LGBMClassifier(**p)
    pipe = Pipeline([("pre", pre), ("clf", clf)])
    pipe.fit(X_train, y_train)
    return pipe


def train_mlp(
    X_train: pd.DataFrame, y_train: pd.Series, *, params: dict[str, Any] | None = None
) -> Pipeline:
    p = {
        "hidden_layer_sizes": (64, 32),
        "max_iter": 400,
        "early_stopping": True,
        "validation_fraction": 0.15,
        "n_iter_no_change": 15,
        "random_state": 42,
    }
    if params:
        p.update(params)
    pre = build_preprocessor(X_train)
    clf = MLPClassifier(**p)
    pipe = Pipeline([("pre", pre), ("scale", StandardScaler()), ("clf", clf)])
    pipe.fit(X_train, y_train)
    return pipe


def predict_pipeline(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def train_hgb_sklearn(X_train: pd.DataFrame, y_train: pd.Series):
    """Repli sklearn si LightGBM natif indisponible (compat webapp historique)."""
    return train_hgb(X_train, y_train)


# Alias rétrocompatibilité
train_logistic_regression = train_logistic
