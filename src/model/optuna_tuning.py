"""Optimisation hyperparamètres Optuna (validation PR-AUC)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from src.model.trainers import (
    train_hist_gradient_boosting,
    train_lightgbm,
    train_mlp,
    train_random_forest,
)


def _pr_auc(y_true, proba) -> float:
    return float(average_precision_score(y_true, proba))


def tune_random_forest(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    n_trials: int = 25,
) -> dict[str, Any]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 80, 280, step=20),
            "max_depth": trial.suggest_int("max_depth", 4, 12),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 4, 24),
        }
        model = train_random_forest(X_tr, y_tr, params=params)
        proba = model.predict_proba(X_va)[:, 1]
        return _pr_auc(y_va, proba)

    study = optuna.create_study(direction="maximize", study_name="rf")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


def tune_lightgbm(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    n_trials: int = 25,
) -> dict[str, Any] | None:
    try:
        import optuna
    except ImportError:
        return None
    if train_lightgbm(X_tr, y_tr) is None:
        return None

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 80, 260, step=20),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 5.0, log=True),
        }
        model = train_lightgbm(X_tr, y_tr, params=params)
        if model is None:
            raise optuna.TrialPruned()
        proba = model.predict_proba(X_va)[:, 1]
        return _pr_auc(y_va, proba)

    study = optuna.create_study(direction="maximize", study_name="lightgbm")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


def tune_mlp(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    n_trials: int = 20,
) -> dict[str, Any]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        h1 = trial.suggest_int("h1", 32, 128, step=16)
        h2 = trial.suggest_int("h2", 16, 64, step=16)
        params = {
            "hidden_layer_sizes": (h1, h2),
            "alpha": trial.suggest_float("alpha", 1e-5, 1e-2, log=True),
            "learning_rate_init": trial.suggest_float(
                "learning_rate_init", 1e-4, 5e-3, log=True
            ),
        }
        model = train_mlp(X_tr, y_tr, params=params)
        proba = model.predict_proba(X_va)[:, 1]
        return _pr_auc(y_va, proba)

    study = optuna.create_study(direction="maximize", study_name="mlp")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = study.best_params
    return {
        "hidden_layer_sizes": (best["h1"], best["h2"]),
        "alpha": best["alpha"],
        "learning_rate_init": best["learning_rate_init"],
    }


def tune_hist_gradient_boosting(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    n_trials: int = 20,
) -> dict[str, Any]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "max_iter": trial.suggest_int("max_iter", 80, 220, step=20),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 8, 40),
            "l2_regularization": trial.suggest_float(
                "l2_regularization", 0.1, 5.0, log=True
            ),
        }
        model = train_hist_gradient_boosting(X_tr, y_tr, params=params)
        proba = model.predict_proba(X_va)[:, 1]
        return _pr_auc(y_va, proba)

    study = optuna.create_study(direction="maximize", study_name="hist_gb")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


def apply_optuna(
    key: str,
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_va: pd.DataFrame,
    y_va: pd.Series,
    *,
    n_trials: int,
) -> dict[str, Any] | None:
    if key == "random_forest":
        return tune_random_forest(X_tr, y_tr, X_va, y_va, n_trials=n_trials)
    if key == "hist_gradient_boosting":
        return tune_hist_gradient_boosting(X_tr, y_tr, X_va, y_va, n_trials=n_trials)
    if key == "lightgbm":
        return tune_lightgbm(X_tr, y_tr, X_va, y_va, n_trials=n_trials)
    if key == "mlp":
        return tune_mlp(X_tr, y_tr, X_va, y_va, n_trials=n_trials)
    return None
