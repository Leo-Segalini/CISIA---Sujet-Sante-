"""Surveillance prod : taux d'alertes, prévalence, dérive simple des features."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.paths import ProjectPaths
from src.model.inference import predict_proba, threshold_for
from src.model.prepare import by_split, split_xy


def _baseline_path(paths: ProjectPaths, score_name: str) -> Path:
    d = paths.models / "monitoring"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{score_name}_baseline.json"


def write_monitoring_baseline(
    paths: ProjectPaths,
    score_name: str,
    features: pd.DataFrame,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Baseline = stats train + taux d'alerte test au moment de la promotion."""
    import joblib

    X, y, split = split_xy(features)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_te, y_te = by_split(X, y, split, "test")

    numeric = X_tr.select_dtypes(include=[np.number])
    feature_means = {c: float(numeric[c].mean()) for c in numeric.columns}

    bundle = joblib.load(paths.models / f"{score_name}_bundle.joblib")
    retenu = metrics["retenu"]
    proba = predict_proba(bundle, retenu, X_te)
    thr = threshold_for(metrics, retenu)
    alert_rate = float((proba >= thr).mean())

    baseline = {
        "score": score_name,
        "retenu": retenu,
        "created_at": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "n_train": int(len(X_tr)),
        "prevalence_train": float(y_tr.mean()),
        "prevalence_test": float(y_te.mean()),
        "alert_rate_test": alert_rate,
        "threshold": thr,
        "feature_means_train": feature_means,
        "alert_rate_warn_abs_delta": 0.10,
        "drift_warn_mean_abs": 0.35,
    }
    path = _baseline_path(paths, score_name)
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline


def _load_baseline(paths: ProjectPaths, score_name: str) -> dict[str, Any] | None:
    path = _baseline_path(paths, score_name)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_drift(
    paths: ProjectPaths,
    score_name: str,
    features: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Compare features actuelles + taux d'alerte test à la baseline de promotion."""
    import joblib

    baseline = _load_baseline(paths, score_name)
    if baseline is None:
        return {"score": score_name, "status": "no_baseline", "ok": False}

    if features is None:
        parquet = paths.curated / f"features_{score_name}.parquet"
        if not parquet.exists():
            return {"score": score_name, "status": "no_features", "ok": False}
        features = pd.read_parquet(parquet)

    X, y, split = split_xy(features)
    X_te, y_te = by_split(X, y, split, "test")
    numeric = X_te.select_dtypes(include=[np.number])
    means = {c: float(numeric[c].mean()) for c in numeric.columns if c in baseline["feature_means_train"]}

    deltas = []
    for col, base_mean in baseline["feature_means_train"].items():
        if col not in means:
            continue
        scale = abs(base_mean) if abs(base_mean) > 1e-6 else 1.0
        deltas.append(abs(means[col] - base_mean) / scale)
    drift_score = float(np.mean(deltas)) if deltas else 0.0

    bundle_path = paths.models / f"{score_name}_bundle.joblib"
    metrics_path = paths.models / f"{score_name}_metrics.json"
    if not bundle_path.exists() or not metrics_path.exists():
        return {"score": score_name, "status": "no_model", "ok": False}

    bundle = joblib.load(bundle_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    retenu = metrics.get("retenu", baseline["retenu"])
    proba = predict_proba(bundle, retenu, X_te)
    thr = threshold_for(metrics, retenu)
    alert_rate = float((proba >= thr).mean())
    alert_delta = abs(alert_rate - float(baseline["alert_rate_test"]))

    warn_alert = alert_delta >= float(baseline.get("alert_rate_warn_abs_delta", 0.10))
    warn_drift = drift_score >= float(baseline.get("drift_warn_mean_abs", 0.35))
    ok = not warn_alert and not warn_drift

    return {
        "score": score_name,
        "status": "ok" if ok else "warn",
        "ok": ok,
        "retenu": retenu,
        "alert_rate_test": alert_rate,
        "alert_rate_baseline": baseline["alert_rate_test"],
        "alert_rate_delta": alert_delta,
        "drift_score": drift_score,
        "prevalence_test": float(y_te.mean()),
        "threshold": thr,
        "warnings": {
            "alert_rate": warn_alert,
            "feature_drift": warn_drift,
        },
        "checked_at": datetime.now(UTC).isoformat(),
    }


def build_monitoring_snapshot(paths: ProjectPaths) -> dict[str, Any]:
    out = {"checked_at": datetime.now(UTC).isoformat(), "scores": {}}
    for score_name in ("score_sortie", "score_tele"):
        out["scores"][score_name] = evaluate_drift(paths, score_name)
    out["global_ok"] = all(
        s.get("ok") for s in out["scores"].values() if s.get("status") != "no_baseline"
    )
    return out
