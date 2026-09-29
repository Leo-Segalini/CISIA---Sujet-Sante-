"""Orchestration ré-entraînement (pipeline données + modèles)."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.paths import ProjectPaths, get_project_root
from src.data.pipeline import run_pipeline
from src.data.quality_report import export_quality_report
from src.mlops.fhir_client import FhirConfig, ingest_fhir_patient
from src.mlops.registry import register_version
from src.model.bias import bias_table
from src.model.benchmark import run_benchmark
from src.model.explain import shap_top_features
from src.model.prepare import by_split, split_xy
from src.model.inference import predict_proba, threshold_for
from src.model.train import predict_hgb


@dataclass
class RetrainState:
    status: str = "idle"
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    last_result: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "last_error": self.last_error,
                "last_result": self.last_result,
            }


_STATE = RetrainState()


def get_retrain_state() -> dict[str, Any]:
    return _STATE.snapshot()


def _set(**kwargs) -> None:
    with _STATE._lock:
        for k, v in kwargs.items():
            setattr(_STATE, k, v)


def _post_train_artifacts(
    paths: ProjectPaths, score_name: str, features: pd.DataFrame, metrics: dict
) -> None:
    import joblib

    bundle = joblib.load(paths.models / f"{score_name}_bundle.joblib")
    X, y, split = split_xy(features)
    X_te, y_te = by_split(X, y, split, "test")
    retenu = metrics["retenu"]
    proba = predict_proba(bundle, retenu, X_te)
    thr = threshold_for(metrics, retenu)
    pred = (proba >= thr).astype(int)
    bias = bias_table(X_te, y_te, pd.Series(pred, index=X_te.index))
    bias.to_csv(paths.models / f"{score_name}_biais.csv", index=False)
    if "hgb" in bundle and "coder" in bundle:
        shap_df = shap_top_features(bundle["coder"], bundle["hgb"], X)
        shap_df.to_csv(paths.models / f"{score_name}_shap.csv", index=False)


def run_full_retrain(
    paths: ProjectPaths | None = None,
    *,
    use_optuna: bool = False,
    optuna_trials: int = 25,
    horizon_tele: int = 7,
    source: str = "api",
) -> dict[str, Any]:
    """Pipeline données + qualité + benchmark + déploiement + registry."""
    paths = paths or ProjectPaths(root=get_project_root())
    _set(
        status="running",
        started_at=datetime.now(UTC).isoformat(),
        finished_at=None,
        last_error=None,
    )
    try:
        pipeline_out = run_pipeline(paths, horizon_tele=horizon_tele)
        qualite = export_quality_report(paths)
        results: dict[str, Any] = {
            "pipeline": {k: str(v) for k, v in pipeline_out.items()},
            "qualite_html": str(qualite["html"]),
            "scores": {},
        }
        for score_name in ("score_sortie", "score_tele"):
            parquet = paths.curated / f"features_{score_name}.parquet"
            features = pd.read_parquet(parquet)
            # Import local : évite le cycle deploy → mlops.__init__ → retrain → deploy
            from src.model.deploy import train_score

            metrics = train_score(
                features,
                score_name=score_name,
                paths=paths,
                use_optuna=use_optuna,
                optuna_trials=optuna_trials,
            )
            _post_train_artifacts(paths, score_name, features, metrics)
            version = register_version(paths, score_name=score_name, metrics=metrics, source=source)
            results["scores"][score_name] = {
                "retenu": metrics["retenu"],
                "ranking": metrics["ranking_test_pr_auc"],
                "version": version,
            }
        _set(status="success", finished_at=datetime.now(UTC).isoformat(), last_result=results)
        try:
            from src.web.services import reload_store

            reload_store()
        except Exception:
            pass
        return results
    except Exception as exc:
        _set(
            status="error",
            finished_at=datetime.now(UTC).isoformat(),
            last_error=str(exc),
        )
        raise


def run_retrain_async(**kwargs) -> None:
    def _job() -> None:
        try:
            run_full_retrain(**kwargs)
        except Exception:
            pass

    threading.Thread(target=_job, daemon=True).start()


def ingest_fhir_and_append(
    paths: ProjectPaths,
    patient_id: str,
    *,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    """Ingère un patient FHIR sandbox et fusionne dans sejours.csv (démo uniquement)."""
    cfg = FhirConfig(base_url=fhir_base_url or os.environ.get("FHIR_BASE_URL", FhirConfig.base_url))
    new_rows = ingest_fhir_patient(patient_id, config=cfg)
    if new_rows.empty:
        return {"ingested": 0, "message": "Aucun séjour FHIR"}
    sejours_path = paths.raw / "sejours.csv"
    paths.ensure_data_dirs()
    if not sejours_path.exists():
        from src.data.load import copy_sources_to_raw

        copy_sources_to_raw(paths)
    existing = pd.read_csv(sejours_path)
    merged = pd.concat([existing, new_rows], ignore_index=True)
    merged.drop_duplicates(subset=["SejourID"], keep="last", inplace=True)
    # Écrit uniquement dans data/raw — jamais dans donnees/ (sources immuables)
    merged.to_csv(sejours_path, index=False)
    return {
        "ingested": int(len(new_rows)),
        "patient_id": patient_id,
        "fhir_base": cfg.base_url,
        "total_sejours": int(len(merged)),
    }
