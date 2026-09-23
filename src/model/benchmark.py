"""Benchmark multi-modèles sur les mêmes splits patient-level."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.data.paths import ProjectPaths
from src.model.metrics import best_f2_threshold, classification_metrics
from src.model.optuna_tuning import apply_optuna
from src.model.prepare import by_split, split_xy
from src.model.report import write_benchmark_report
from src.model.train import evaluate_pair, train_logistic
from src.model.trainers import (
    predict_pipeline,
    predict_reference,
    train_lightgbm,
    train_mlp,
    train_random_forest,
    train_reference,
)
from src.model.train import predict_logistic

PredictFn = Callable[[Any, pd.DataFrame], np.ndarray]
TrainFn = Callable[[pd.DataFrame, pd.Series], Any]


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    train: TrainFn
    predict: PredictFn
    optional: bool = False
    tunable: bool = False


def _predict_logistic_artifact(model, X: pd.DataFrame) -> np.ndarray:
    return predict_logistic(model, X)


def _predict_reference_artifact(model, X: pd.DataFrame) -> np.ndarray:
    return predict_reference(model, X)


def model_catalog() -> list[ModelSpec]:
    return [
        ModelSpec(
            "reference",
            "Référence (prévalence train)",
            train_reference,
            _predict_reference_artifact,
        ),
        ModelSpec(
            "logistic",
            "Régression logistique",
            train_logistic,
            _predict_logistic_artifact,
        ),
        ModelSpec(
            "random_forest",
            "Forêt aléatoire",
            train_random_forest,
            predict_pipeline,
            tunable=True,
        ),
        ModelSpec(
            "lightgbm",
            "LightGBM",
            train_lightgbm,
            predict_pipeline,
            optional=True,
            tunable=True,
        ),
        ModelSpec(
            "mlp",
            "MLP (réseau de neurones)",
            train_mlp,
            predict_pipeline,
            tunable=True,
        ),
    ]


def _train_one(
    spec: ModelSpec,
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    *,
    tuned_params: dict[str, Any] | None = None,
) -> tuple[str, Any | None, str | None]:
    try:
        if tuned_params and spec.tunable:
            if spec.key == "random_forest":
                artifact = train_random_forest(X_tr, y_tr, params=tuned_params)
            elif spec.key == "lightgbm":
                artifact = train_lightgbm(X_tr, y_tr, params=tuned_params)
            elif spec.key == "mlp":
                artifact = train_mlp(X_tr, y_tr, params=tuned_params)
            else:
                artifact = spec.train(X_tr, y_tr)
        else:
            artifact = spec.train(X_tr, y_tr)
        if artifact is None:
            return spec.key, None, "dépendance absente ou entraînement ignoré"
        return spec.key, artifact, None
    except Exception as exc:  # noqa: BLE001
        return spec.key, None, str(exc)


def _evaluate_model(
    spec: ModelSpec,
    artifact: Any,
    y_va: pd.Series,
    X_va: pd.DataFrame,
    y_te: pd.Series,
    X_te: pd.DataFrame,
) -> dict:
    p_va = spec.predict(artifact, X_va)
    p_te = spec.predict(artifact, X_te)
    return evaluate_pair(spec.key, y_va, p_va, y_te, p_te)


def _curve_points(y_true, proba, *, kind: str) -> list[dict[str, float]]:
    from sklearn.metrics import precision_recall_curve, roc_curve

    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    if kind == "roc":
        fpr, tpr, _ = roc_curve(y_true, proba)
        return [{"x": float(a), "y": float(b)} for a, b in zip(fpr, tpr)]
    precision, recall, _ = precision_recall_curve(y_true, proba)
    return [{"x": float(r), "y": float(p)} for r, p in zip(recall, precision)]


def run_benchmark(
    features: pd.DataFrame,
    *,
    score_name: str,
    paths: ProjectPaths,
    parallel: bool = True,
    use_optuna: bool = False,
    optuna_trials: int = 25,
) -> dict:
    """Entraîne tous les modèles disponibles et produit rapport JSON + HTML."""
    X, y, split = split_xy(features)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_va, y_va = by_split(X, y, split, "val")
    X_te, y_te = by_split(X, y, split, "test")

    catalog = model_catalog()
    optuna_params: dict[str, dict[str, Any]] = {}
    if use_optuna:
        for spec in catalog:
            if not spec.tunable:
                continue
            best = apply_optuna(
                spec.key, X_tr, y_tr, X_va, y_va, n_trials=optuna_trials
            )
            if best:
                optuna_params[spec.key] = best

    trained: dict[str, Any] = {}
    skipped: dict[str, str] = {}

    def _run(spec: ModelSpec) -> tuple[str, Any | None, str | None]:
        return _train_one(
            spec, X_tr, y_tr, tuned_params=optuna_params.get(spec.key)
        )

    if parallel:
        with ThreadPoolExecutor(max_workers=min(5, len(catalog))) as pool:
            futures = {pool.submit(_run, spec): spec for spec in catalog}
            for fut in as_completed(futures):
                key, artifact, err = fut.result()
                if artifact is None:
                    skipped[key] = err or "non disponible"
                else:
                    trained[key] = (futures[fut], artifact)
    else:
        for spec in catalog:
            key, artifact, err = _run(spec)
            if artifact is None:
                skipped[key] = err or "non disponible"
            else:
                trained[key] = (spec, artifact)

    results: dict[str, dict] = {}
    curves: dict[str, dict] = {}
    for key, (spec, artifact) in trained.items():
        ev = _evaluate_model(spec, artifact, y_va, X_va, y_te, X_te)
        entry: dict[str, Any] = {
            "label": spec.label,
            **ev,
            "curves": {
                "roc_val": _curve_points(y_va, spec.predict(artifact, X_va), kind="roc"),
                "pr_val": _curve_points(y_va, spec.predict(artifact, X_va), kind="pr"),
                "roc_test": _curve_points(y_te, spec.predict(artifact, X_te), kind="roc"),
                "pr_test": _curve_points(y_te, spec.predict(artifact, X_te), kind="pr"),
            },
        }
        if key in optuna_params:
            entry["optuna_params"] = optuna_params[key]
        results[key] = entry
        curves[key] = results[key]["curves"]

    if not results:
        raise RuntimeError("Aucun modèle entraîné — vérifier les dépendances.")

    ranking = sorted(
        results.items(),
        key=lambda item: item[1]["test"]["pr_auc"],
        reverse=True,
    )
    retenu = ranking[0][0]

    report = {
        "score": score_name,
        "n_train": int(len(y_tr)),
        "n_val": int(len(y_va)),
        "n_test": int(len(y_te)),
        "modeles": results,
        "skipped": skipped,
        "ranking_test_pr_auc": [k for k, _ in ranking],
        "retenu": retenu,
        "retenu_label": results[retenu]["label"],
        "optuna": use_optuna,
        "optuna_trials": optuna_trials if use_optuna else 0,
        "note": (
            "Splits patient-level identiques pour tous les modèles. "
            "Seuil F2 max sur validation. Classement final sur PR-AUC test. "
            "Modèles tunables (RF, LightGBM, MLP) : Optuna sur PR-AUC validation."
        ),
    }

    paths.ensure_data_dirs()
    out_dir = paths.models / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{score_name}_benchmark.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = write_benchmark_report(report, out_dir / f"{score_name}_benchmark.html", curves=curves)
    report["paths"] = {"json": str(json_path), "html": str(html_path)}
    return report
