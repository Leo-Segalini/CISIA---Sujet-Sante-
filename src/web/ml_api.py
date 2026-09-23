"""Routes API MLOps (ré-entraînement, FHIR, registry)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException

from src.data.paths import ProjectPaths, get_project_root
from src.mlops.fhir_client import FhirConfig
from src.mlops.registry import list_versions
from src.mlops.retrain import get_retrain_state, ingest_fhir_and_append, run_full_retrain
from src.web.services import reload_store

router = APIRouter(prefix="/api/ml", tags=["mlops"])


def _check_ml_key(x_ml_api_key: str | None) -> None:
    expected = os.environ.get("ML_API_KEY", "").strip()
    if not expected:
        return
    if x_ml_api_key != expected:
        raise HTTPException(status_code=401, detail="Clé ML_API_KEY invalide")


@router.get("/status")
def ml_status():
    paths = ProjectPaths(root=get_project_root())
    return {
        "retrain": get_retrain_state(),
        "registry": {
            "score_sortie": list_versions(paths, "score_sortie")[-3:],
            "score_tele": list_versions(paths, "score_tele")[-3:],
        },
        "fhir_default": FhirConfig().base_url,
    }


@router.post("/retrain")
def ml_retrain(
    payload: dict | None = None,
    x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
):
    _check_ml_key(x_ml_api_key)
    state = get_retrain_state()
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Ré-entraînement déjà en cours")
    body = payload or {}
    use_optuna = bool(body.get("optuna", False))
    trials = int(body.get("trials", 25))
    paths = ProjectPaths(root=get_project_root())

    def _done_callback():
        reload_store()

    def _run():
        from src.mlops.retrain import run_full_retrain

        try:
            run_full_retrain(
                paths,
                use_optuna=use_optuna,
                optuna_trials=trials,
                source="api",
            )
        finally:
            reload_store()

    import threading

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "optuna": use_optuna, "trials": trials}


@router.post("/ingest/fhir")
def ml_ingest_fhir(
    payload: dict,
    x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
):
    _check_ml_key(x_ml_api_key)
    patient_id = str(payload.get("patient_id") or "").strip()
    if not patient_id:
        raise HTTPException(status_code=422, detail="patient_id requis")
    paths = ProjectPaths(root=get_project_root())
    try:
        result = ingest_fhir_and_append(
            paths,
            patient_id,
            fhir_base_url=payload.get("fhir_base_url"),
        )
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result
