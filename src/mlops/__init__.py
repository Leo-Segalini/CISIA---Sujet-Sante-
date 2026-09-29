"""Package MLOps — ré-entraînement, registry, FHIR.

Les imports lourds (retrain) sont en lazy dans ``__getattr__`` pour éviter
le cycle : ``deploy`` → ``mlops.production`` → ``mlops.__init__`` → ``retrain`` → ``deploy``.
"""

from src.mlops.fhir_client import FhirConfig, ingest_fhir_patient
from src.mlops.production import PRODUCTION_MODELS, promote_all_to_production
from src.mlops.registry import list_versions, register_version

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

_LAZY = {
    "get_retrain_state": ("src.mlops.retrain", "get_retrain_state"),
    "run_full_retrain": ("src.mlops.retrain", "run_full_retrain"),
    "run_retrain_async": ("src.mlops.retrain", "run_retrain_async"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
