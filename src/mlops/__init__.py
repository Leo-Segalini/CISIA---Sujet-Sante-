"""Package MLOps — ré-entraînement, registry, FHIR."""

from src.mlops.fhir_client import FhirConfig, ingest_fhir_patient
from src.mlops.production import PRODUCTION_MODELS, promote_all_to_production
from src.mlops.registry import list_versions, register_version
from src.mlops.retrain import get_retrain_state, run_full_retrain, run_retrain_async

__all__ = [
    "FhirConfig",
    "PRODUCTION_MODELS",
    "get_retrain_state",
    "ingest_fhir_patient",
    "list_versions",
    "promote_all_to_production",
    "register_version",
    "run_full_retrain",
    "run_retrain_async",
]
