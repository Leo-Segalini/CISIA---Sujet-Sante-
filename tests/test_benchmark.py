"""Tests benchmark et explication risque patient."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.paths import ProjectPaths, get_project_root
from src.model.benchmark import model_catalog, run_benchmark
from src.model.explain_patient import build_explication_risque_30j, facteurs_risque_patient
from src.web.services import predict_sejour


@pytest.fixture(scope="module")
def features_sortie() -> pd.DataFrame:
    path = ProjectPaths(root=get_project_root()).curated / "features_score_sortie.parquet"
    if not path.exists():
        pytest.skip("features_score_sortie.parquet absent — lancer run_pipeline.py")
    return pd.read_parquet(path)


def test_model_catalog_has_core_models():
    keys = {s.key for s in model_catalog()}
    assert "reference" in keys
    assert "logistic" in keys
    assert "random_forest" in keys
    assert "hist_gradient_boosting" in keys
    assert "lightgbm" in keys
    assert "mlp" in keys


def test_hist_gradient_boosting_trains(features_sortie: pd.DataFrame):
    from src.model.prepare import by_split, split_xy
    from src.model.trainers import (
        predict_hist_gradient_boosting,
        train_hist_gradient_boosting,
    )

    X, y, split = split_xy(features_sortie)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_tr, y_tr = X_tr.head(400), y_tr.head(400)
    art = train_hist_gradient_boosting(X_tr, y_tr)
    proba = predict_hist_gradient_boosting(art, X_tr.head(20))
    assert len(proba) == 20
    assert ((proba >= 0) & (proba <= 1)).all()


def test_build_explication_risque_text():
    text = build_explication_risque_30j(
        proba_pct=42,
        seuil_pct=35,
        alerte=True,
        facteurs=[
            {
                "libelle": "Âge à l’admission",
                "valeur": "82",
                "impact": "hausse",
                "shap": 0.1,
            }
        ],
    )
    assert "42 %" in text
    assert "suivi renforcé" in text.lower() or "seuil" in text.lower()


def test_predict_sejour_has_risk_explanation():
    from src.web.services import list_sejours

    sej = list_sejours(page_size=1)["items"][0]["SejourID"]
    detail = predict_sejour(sej)
    assert "explication_risque_30j" in detail
    assert detail["explication_risque_30j"]
    assert "facteurs_risque_patient" in detail
    assert isinstance(detail["facteurs_risque_patient"], list)


@pytest.mark.slow
def test_run_benchmark_score_sortie(features_sortie: pd.DataFrame, tmp_path: Path):
    paths = ProjectPaths(root=get_project_root())
    # Écriture dans tmp pour ne pas écraser les artefacts de prod
    class _Paths:
        models = tmp_path / "models"

        def ensure_data_dirs(self):
            self.models.mkdir(parents=True, exist_ok=True)

    report = run_benchmark(features_sortie, score_name="score_sortie_test", paths=_Paths())
    assert report["retenu"] in report["modeles"]
    assert len(report["ranking_test_pr_auc"]) >= 2
    assert (tmp_path / "models" / "benchmark" / "score_sortie_test_benchmark.json").exists()
    assert (tmp_path / "models" / "benchmark" / "score_sortie_test_benchmark.html").exists()
