from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.paths import ProjectPaths, get_project_root
from src.data.quality_report import (
    analyze_dataset,
    export_quality_report,
    missing_rates,
)
from src.data.registre import load_registre


@pytest.fixture
def registre() -> pd.DataFrame:
    root = get_project_root()
    return load_registre(root / "docs" / "registres" / "registre_colonnes.csv")


def test_missing_rates_detects_empty_strings():
    df = pd.DataFrame({"a": [1, None, ""], "b": ["x", "y", "z"]})
    rates = missing_rates(df)
    assert rates["a"] == pytest.approx(2 / 3)
    assert rates["b"] == 0.0


def test_analyze_signes_vitaux(registre: pd.DataFrame):
    root = get_project_root()
    paths = ProjectPaths(root=root)
    sv = pd.read_csv(root / "donnees" / "signes_vitaux.csv", nrows=200)
    rep = analyze_dataset("signes_vitaux.csv", sv, registre)
    assert rep["n_lignes"] == 200
    assert "FrequenceCardiaque" in rep["aberrants"] or rep["aberrants"] == {}
    assert "tension_diastole_ge_systole" in rep["mal_notes"] or rep["mal_notes"] == {}


def test_export_quality_report(tmp_path: Path, monkeypatch):
    root = get_project_root()
    paths = ProjectPaths(root=root)

    def _curated(self):
        return tmp_path / "curated"

    monkeypatch.setattr(ProjectPaths, "curated", property(_curated))

    out = export_quality_report(paths)
    assert out["json"].exists()
    assert out["html"].exists()
    assert "rapport_qualite" in out["html"].name
