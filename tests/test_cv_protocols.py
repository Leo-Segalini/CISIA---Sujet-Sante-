"""Tests des protocoles d'entraînement comparatifs."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.paths import ProjectPaths, get_project_root
from src.model.cv_protocols import (
    compare_training_protocols,
    protocol_cv_patient,
    protocol_holdout,
)


@pytest.fixture(scope="module")
def features_sortie() -> pd.DataFrame:
    path = ProjectPaths(root=get_project_root()).curated / "features_score_sortie.parquet"
    if not path.exists():
        pytest.skip("features_score_sortie.parquet absent")
    return pd.read_parquet(path)


def test_holdout_logistic_has_pr_auc(features_sortie: pd.DataFrame):
    out = protocol_holdout(features_sortie, "logistic")
    assert out["protocol"] == "holdout_patient"
    assert 0.0 <= out["summary"]["pr_auc"] <= 1.0


def test_cv_patient_runs(features_sortie: pd.DataFrame):
    out = protocol_cv_patient(features_sortie, "logistic", n_splits=3)
    assert out["n_folds"] >= 2
    assert "pr_auc_std" in out["summary"]


def test_compare_all_protocols_smoke(features_sortie: pd.DataFrame):
    # Sous-échantillon pour vitesse CI
    sample = features_sortie.sample(n=min(120, len(features_sortie)), random_state=42)
    # garder assez de patients
    if sample["PatientID"].nunique() < 30:
        sample = features_sortie
    df = compare_training_protocols(
        sample,
        score_name="score_sortie",
        models=("logistic",),
        protocols=("holdout_patient", "cv_patient_k5"),
    )
    assert set(df["protocol"]) >= {"holdout_patient", "cv_patient_k5"}
    assert (df["pr_auc"] > 0).all()
