"""Tests promotion production hôpital."""

from __future__ import annotations

from pathlib import Path

import joblib
import pytest

from src.data.paths import ProjectPaths, get_project_root
from src.mlops.monitoring import build_monitoring_snapshot
from src.mlops.production import PRODUCTION_MODELS, promote_all_to_production
from src.model.inference import score_single
from src.model.prepare import split_xy
import json
import pandas as pd


@pytest.fixture(scope="module")
def paths() -> ProjectPaths:
    return ProjectPaths(root=get_project_root())


def test_promote_production_creates_manifest(paths: ProjectPaths):
    for score in PRODUCTION_MODELS:
        if not (paths.curated / f"features_{score}.parquet").exists():
            pytest.skip("curated manquant")
    result = promote_all_to_production(paths, source="test")
    assert Path(result["manifest"]).is_file()
    for score, model in PRODUCTION_MODELS.items():
        bundle = joblib.load(paths.models / f"{score}_bundle.joblib")
        assert bundle["retenu"] == model
        assert bundle.get("calibrated") is not None
        assert bundle.get("production") is True
    snap = build_monitoring_snapshot(paths)
    assert "scores" in snap


def test_score_single_uses_calibrated_bundle(paths: ProjectPaths):
    metrics = json.loads((paths.models / "score_sortie_metrics.json").read_text())
    if not metrics.get("calibrated"):
        pytest.skip("pas encore calibré")
    bundle = joblib.load(paths.models / "score_sortie_bundle.joblib")
    feat = pd.read_parquet(paths.curated / "features_score_sortie.parquet")
    row = feat.loc[feat["split"] == "test"].iloc[[0]]
    X, _, _ = split_xy(row)
    out = score_single(bundle, metrics, X)
    assert "proba" in out
    assert 0.0 <= out["proba"] <= 1.0
