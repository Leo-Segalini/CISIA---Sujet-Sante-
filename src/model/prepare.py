from __future__ import annotations

import pandas as pd

ID_COLS = ("SejourID", "PatientID")
TARGET_COL = "Readmission30j"
SPLIT_COL = "split"
CATEGORICAL_COLS = ("Service", "TypeSejour", "GHM", "Sexe")


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    missing = [c for c in (TARGET_COL, SPLIT_COL) if c not in df.columns]
    if missing:
        raise KeyError(f"Colonnes manquantes: {missing}")
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").astype("Int64")
    if y.isna().any():
        raise ValueError("Cible manquante")
    X = df.drop(columns=[TARGET_COL, *ID_COLS], errors="ignore")
    split = df[SPLIT_COL].astype(str)
    X = X.drop(columns=[SPLIT_COL])
    return X, y.astype(int), split


def by_split(
    X: pd.DataFrame, y: pd.Series, split: pd.Series, name: str
) -> tuple[pd.DataFrame, pd.Series]:
    mask = split == name
    if not mask.any():
        raise ValueError(f"Split vide: {name}")
    return X.loc[mask].copy(), y.loc[mask].copy()
