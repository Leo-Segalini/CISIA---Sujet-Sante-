"""Comparaison de protocoles d'entraînement : hold-out vs CV patient vs CV stratifiée."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

from src.model.metrics import best_f2_threshold, classification_metrics
from src.model.prepare import ID_COLS, SPLIT_COL, TARGET_COL, by_split, split_xy
from src.model.train import predict_logistic, train_logistic
from src.model.trainers import predict_pipeline, train_random_forest

TrainFn = Callable[[pd.DataFrame, pd.Series], Any]
PredictFn = Callable[[Any, pd.DataFrame], np.ndarray]

MODEL_FNS: dict[str, tuple[TrainFn, PredictFn]] = {
    "logistic": (train_logistic, predict_logistic),
    "random_forest": (train_random_forest, predict_pipeline),
}


def _xy_from_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Extrait X, y et PatientID (groupes) sans dépendre de la colonne split."""
    missing = [c for c in (TARGET_COL, "PatientID") if c not in df.columns]
    if missing:
        raise KeyError(f"Colonnes manquantes: {missing}")
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").astype(int)
    groups = df["PatientID"].astype(str)
    drop_cols = [TARGET_COL, *ID_COLS]
    if SPLIT_COL in df.columns:
        drop_cols.append(SPLIT_COL)
    X = df.drop(columns=[c for c in drop_cols if c in df.columns])
    return X, y, groups


def _inner_train_val_by_patient(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    *,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Sépare ~val_ratio des patients du train pour caler le seuil F2."""
    patients = groups.drop_duplicates().to_numpy()
    rng = np.random.default_rng(seed)
    rng.shuffle(patients)
    n_val = max(1, int(len(patients) * val_ratio))
    val_patients = set(patients[:n_val])
    mask_val = groups.isin(val_patients)
    return (
        X.loc[~mask_val].copy(),
        y.loc[~mask_val].copy(),
        X.loc[mask_val].copy(),
        y.loc[mask_val].copy(),
    )


def _eval_once(
    *,
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    model_key: str,
) -> dict[str, float]:
    train_fn, predict_fn = MODEL_FNS[model_key]
    model = train_fn(X_tr, y_tr)
    p_va = predict_fn(model, X_va)
    p_te = predict_fn(model, X_te)
    thr = best_f2_threshold(y_va, p_va)
    return classification_metrics(y_te, p_te, thr)


def protocol_holdout(features: pd.DataFrame, model_key: str) -> dict[str, Any]:
    """Protocole A : split curated train/val/test patient-level."""
    X, y, split = split_xy(features)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_va, y_va = by_split(X, y, split, "val")
    X_te, y_te = by_split(X, y, split, "test")
    metrics = _eval_once(
        X_tr=X_tr,
        y_tr=y_tr,
        X_va=X_va,
        y_va=y_va,
        X_te=X_te,
        y_te=y_te,
        model_key=model_key,
    )
    return {
        "protocol": "holdout_patient",
        "model": model_key,
        "n_folds": 1,
        "folds": [metrics],
        "summary": {**metrics, "pr_auc_std": 0.0, "roc_auc_std": 0.0, "f2_std": 0.0},
    }


def _run_group_cv(
    features: pd.DataFrame,
    model_key: str,
    *,
    protocol: str,
    splitter,
    n_splits: int,
    seed: int = 42,
) -> dict[str, Any]:
    X, y, groups = _xy_from_frame(features)
    fold_metrics: list[dict[str, float]] = []
    # StratifiedGroupKFold expects y aligned with samples
    for fold_idx, (tr_idx, te_idx) in enumerate(
        splitter.split(X, y, groups), start=1
    ):
        X_full_tr, y_full_tr = X.iloc[tr_idx], y.iloc[tr_idx]
        g_full_tr = groups.iloc[tr_idx]
        X_te, y_te = X.iloc[te_idx], y.iloc[te_idx]
        X_tr, y_tr, X_va, y_va = _inner_train_val_by_patient(
            X_full_tr, y_full_tr, g_full_tr, seed=seed + fold_idx
        )
        if len(y_tr) < 10 or len(y_va) < 5 or len(y_te) < 5:
            continue
        # Besoin des deux classes sur val/test pour ROC/PR
        if y_va.nunique() < 2 or y_te.nunique() < 2:
            continue
        m = _eval_once(
            X_tr=X_tr,
            y_tr=y_tr,
            X_va=X_va,
            y_va=y_va,
            X_te=X_te,
            y_te=y_te,
            model_key=model_key,
        )
        m["fold"] = float(fold_idx)
        fold_metrics.append(m)

    if not fold_metrics:
        raise RuntimeError(f"Aucun pli valide pour {protocol} / {model_key}")

    def _mean_std(key: str) -> tuple[float, float]:
        vals = np.array([f[key] for f in fold_metrics], dtype=float)
        return float(vals.mean()), float(vals.std(ddof=0))

    pr_m, pr_s = _mean_std("pr_auc")
    roc_m, roc_s = _mean_std("roc_auc")
    f2_m, f2_s = _mean_std("f2")
    rec_m, _ = _mean_std("recall")
    prec_m, _ = _mean_std("precision")
    return {
        "protocol": protocol,
        "model": model_key,
        "n_folds": len(fold_metrics),
        "folds": fold_metrics,
        "summary": {
            "pr_auc": pr_m,
            "pr_auc_std": pr_s,
            "roc_auc": roc_m,
            "roc_auc_std": roc_s,
            "f2": f2_m,
            "f2_std": f2_s,
            "recall": rec_m,
            "precision": prec_m,
            "n": int(np.mean([f["n"] for f in fold_metrics])),
            "prevalence": float(np.mean([f["prevalence"] for f in fold_metrics])),
        },
    }


def protocol_cv_patient(
    features: pd.DataFrame, model_key: str, *, n_splits: int = 5
) -> dict[str, Any]:
    """Protocole B : GroupKFold patient-level."""
    return _run_group_cv(
        features,
        model_key,
        protocol="cv_patient_k5",
        splitter=GroupKFold(n_splits=n_splits),
        n_splits=n_splits,
    )


def protocol_cv_stratified_patient(
    features: pd.DataFrame, model_key: str, *, n_splits: int = 5
) -> dict[str, Any]:
    """Protocole C : StratifiedGroupKFold (strate = réadmission max du patient)."""
    return _run_group_cv(
        features,
        model_key,
        protocol="cv_stratified_patient_k5",
        splitter=StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42),
        n_splits=n_splits,
    )


PROTOCOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "holdout_patient": protocol_holdout,
    "cv_patient_k5": protocol_cv_patient,
    "cv_stratified_patient_k5": protocol_cv_stratified_patient,
}


def compare_training_protocols(
    features: pd.DataFrame,
    *,
    score_name: str,
    models: tuple[str, ...] = ("logistic", "random_forest"),
    protocols: tuple[str, ...] = (
        "holdout_patient",
        "cv_patient_k5",
        "cv_stratified_patient_k5",
    ),
) -> pd.DataFrame:
    """Exécute tous les protocoles × modèles et renvoie un tableau résumé."""
    rows: list[dict[str, Any]] = []
    for proto in protocols:
        fn = PROTOCOLS[proto]
        for model_key in models:
            result = fn(features, model_key)
            s = result["summary"]
            rows.append(
                {
                    "score": score_name,
                    "protocol": proto,
                    "model": model_key,
                    "n_folds": result["n_folds"],
                    "pr_auc": s["pr_auc"],
                    "pr_auc_std": s.get("pr_auc_std", 0.0),
                    "roc_auc": s["roc_auc"],
                    "roc_auc_std": s.get("roc_auc_std", 0.0),
                    "f2": s["f2"],
                    "f2_std": s.get("f2_std", 0.0),
                    "recall": s["recall"],
                    "precision": s["precision"],
                }
            )
    return pd.DataFrame(rows)
