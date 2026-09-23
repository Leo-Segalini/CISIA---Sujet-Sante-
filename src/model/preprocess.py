"""Préprocesseur tabulaire partagé (imputation + one-hot)."""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.model.prepare import CATEGORICAL_COLS


def cat_cols(X: pd.DataFrame) -> list[str]:
    return [c for c in CATEGORICAL_COLS if c in X.columns]


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    cat = cat_cols(X)
    num = [c for c in X.columns if c not in cat]
    return ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cat,
            ),
        ]
    )
