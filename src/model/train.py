from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.model.metrics import best_f2_threshold, classification_metrics
from src.model.prepare import CATEGORICAL_COLS, by_split, split_xy


def _cat_cols(X: pd.DataFrame) -> list[str]:
    return [c for c in CATEGORICAL_COLS if c in X.columns]


class CategoryToCode:
    """Encode les catégories sur le train seulement (évite une fuite test)."""

    def __init__(self, columns: list[str]):
        self.columns = columns
        self.maps: dict[str, dict[str, int]] = {}

    def fit(self, X: pd.DataFrame, y=None):
        self.maps = {}
        for col in self.columns:
            values = pd.Series(X[col].astype("string")).dropna().unique().tolist()
            self.maps[col] = {str(v): i for i, v in enumerate(sorted(values))}
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        out = X.copy()
        for col in self.columns:
            mapping = self.maps[col]
            coded = out[col].astype("string").map(mapping)
            out[col] = pd.to_numeric(coded, errors="coerce")
        return out

    def fit_transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        return self.fit(X).transform(X)


def train_logistic(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    cat = _cat_cols(X_train)
    num = [c for c in X_train.columns if c not in cat]
    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        (
                            "oh",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                cat,
            ),
        ]
    )
    clf = LogisticRegression(max_iter=4000, class_weight="balanced")
    pipe = Pipeline([("pre", pre), ("scale", StandardScaler()), ("clf", clf)])
    pipe.fit(X_train, y_train)
    return pipe


def train_hgb(
    X_train: pd.DataFrame, y_train: pd.Series
) -> tuple[CategoryToCode, HistGradientBoostingClassifier]:
    coder = CategoryToCode(_cat_cols(X_train))
    Xt = coder.fit_transform(X_train)
    cat_idx = [Xt.columns.get_loc(c) for c in coder.columns]
    clf = HistGradientBoostingClassifier(
        max_depth=4,
        max_iter=120,
        learning_rate=0.05,
        min_samples_leaf=20,
        l2_regularization=1.0,
        class_weight="balanced",
        categorical_features=cat_idx if cat_idx else None,
        random_state=42,
    )
    clf.fit(Xt, y_train)
    return coder, clf


def predict_logistic(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def predict_hgb(
    coder: CategoryToCode, clf: HistGradientBoostingClassifier, X: pd.DataFrame
) -> np.ndarray:
    return clf.predict_proba(coder.transform(X))[:, 1]


def evaluate_pair(name: str, y_val, p_val, y_test, p_test) -> dict:
    threshold = best_f2_threshold(y_val, p_val)
    return {
        "modele": name,
        "val": classification_metrics(y_val, p_val, threshold),
        "test": classification_metrics(y_test, p_test, threshold),
    }
