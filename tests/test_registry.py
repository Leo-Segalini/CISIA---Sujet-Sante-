"""Tests du registre déclaratif (sources + étapes extensibles)."""

from __future__ import annotations

import pandas as pd

from src.data.registry import (
    CSV_FILES,
    PipelineContext,
    PipelineStep,
    clear_pipeline_steps,
    describe_pipeline,
    list_pipeline_steps,
    list_sources,
    register_pipeline_step,
    sources_dataframe,
)


def test_csv_files_alignes_sur_sources():
    assert len(CSV_FILES) == 11
    assert "patients.csv" in CSV_FILES
    names = [s.filename for s in list_sources(required_only=True)]
    assert list(CSV_FILES) == names


def test_sources_dataframe_jupyter():
    df = sources_dataframe()
    assert {"fichier", "libelle", "requis"}.issubset(df.columns)
    assert len(df) == len(list_sources())


def test_describe_pipeline_default_steps():
    clear_pipeline_steps()
    df = describe_pipeline()
    assert len(df) >= 7
    assert "copy_raw" in set(df["id"])
    assert "export_curated" in set(df["id"])
    assert list(df["ordre"]) == list(range(1, len(df) + 1))


def test_register_custom_step_extension():
    clear_pipeline_steps()
    # Charge les défauts
    list_pipeline_steps()
    before = len(list_pipeline_steps())

    called = {"ok": False}

    def step_extra(ctx: PipelineContext) -> None:
        called["ok"] = True
        ctx.meta["extra"] = True

    register_pipeline_step(
        PipelineStep(
            id="test_extra_block",
            title="Bloc test",
            description="Extension unitaire",
            run=step_extra,
            phase="features",
        )
    )
    steps = list_pipeline_steps()
    assert len(steps) == before + 1
    assert steps[-1].id == "test_extra_block"

    # Nettoyage pour les autres tests
    clear_pipeline_steps()
    list_pipeline_steps()  # recharger défauts


def test_paths_csv_files_compat():
    from src.data.paths import CSV_FILES as CF_PATHS

    assert CF_PATHS == CSV_FILES
