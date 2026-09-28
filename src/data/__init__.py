"""Package données CISIA — pipeline déclaratif via ``registry``."""

from src.data.pipeline import (
    describe_pipeline,
    list_pipeline_steps,
    list_sources,
    run_pipeline,
    sources_dataframe,
)
from src.data.registry import CSV_FILES, SourceSpec

__all__ = [
    "CSV_FILES",
    "SourceSpec",
    "describe_pipeline",
    "list_pipeline_steps",
    "list_sources",
    "run_pipeline",
    "sources_dataframe",
]
