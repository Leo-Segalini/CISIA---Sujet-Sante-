"""Tests nettoyage constantes vitales."""

from __future__ import annotations

import pandas as pd

from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root
from src.data.vitals import enrich_signes_vitaux, historique_constantes_sejour, signes_valides


def test_enrich_flags_tension_incoherente():
    df = pd.DataFrame(
        {
            "ConstanteID": ["SV-1"],
            "SejourID": ["SEJ-1"],
            "Horodatage": ["2024-01-01 10:00:00"],
            "FrequenceCardiaque": [80.0],
            "TensionSystolique": [120.0],
            "TensionDiastolique": [125.0],
            "Temperature": [37.0],
            "FrequenceRespiratoire": [16.0],
            "SpO2": [96.0],
        }
    )
    out = enrich_signes_vitaux(df)
    assert bool(out.loc[0, "flag_tension_incoherente"]) is True
    assert bool(out.loc[0, "exclue"]) is True
    assert "incohérente" in out.loc[0, "motifs_exclusion"][0].lower()


def test_signes_valides_exclut_aberrant():
    df = pd.DataFrame(
        {
            "ConstanteID": ["SV-1", "SV-2"],
            "SejourID": ["SEJ-1", "SEJ-1"],
            "Horodatage": ["2024-01-01 10:00:00", "2024-01-01 11:00:00"],
            "FrequenceCardiaque": [80.0, 5.0],
            "TensionSystolique": [120.0, 118.0],
            "TensionDiastolique": [70.0, 68.0],
            "Temperature": [37.0, 36.8],
            "FrequenceRespiratoire": [16.0, 15.0],
            "SpO2": [96.0, 97.0],
        }
    )
    valid = signes_valides(df)
    assert len(valid) == 1
    assert valid.iloc[0]["ConstanteID"] == "SV-1"


def test_historique_constantes_sejour_from_dataset():
    paths = ProjectPaths(root=get_project_root())
    sv = load_csv(paths, "signes_vitaux.csv", from_raw=False)
    enriched = enrich_signes_vitaux(sv)
    sej = str(enriched["SejourID"].iloc[0])
    hist = historique_constantes_sejour(enriched, sej)
    assert hist["total"] > 0
    assert hist["retenues"] + hist["exclues"] == hist["total"]
    assert "FrequenceCardiaque" in hist["mesures"][0]
    assert "plages_reference" in hist
