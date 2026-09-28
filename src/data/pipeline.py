"""Orchestration pipeline — exécute les étapes du registre."""

from __future__ import annotations

from pathlib import Path

from src.data.paths import ProjectPaths
from src.data.registry import (
    PipelineContext,
    describe_pipeline,
    list_pipeline_steps,
    list_sources,
    sources_dataframe,
)


def run_pipeline(paths: ProjectPaths, *, horizon_tele: int = 7) -> dict[str, Path]:
    """
    Exécute toutes les étapes enregistrées (défauts + extensions).

    Retourne les chemins d’artefacts curated (même contrat qu’avant).
    """
    ctx = PipelineContext(paths=paths, horizon_tele=horizon_tele)
    for step in list_pipeline_steps():
        step.run(ctx)
    return dict(ctx.artifacts)


# Réexport Jupyter-friendly
__all__ = [
    "run_pipeline",
    "describe_pipeline",
    "list_pipeline_steps",
    "list_sources",
    "sources_dataframe",
]
