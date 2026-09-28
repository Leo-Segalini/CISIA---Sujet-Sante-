import pandas as pd

from src.data.features_sortie import (
    aggregate_biologie_pre_sortie,
    aggregate_medications_detail,
    aggregate_pathologies,
)


def test_biologie_ignore_post_sortie():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "DateSortie": ["2024-01-10 12:00:00"],
        }
    )
    bio = pd.DataFrame(
        {
            "SejourID": ["S1", "S1"],
            "DatePrelevement": ["2024-01-09 08:00:00", "2024-01-11 08:00:00"],
            "Panel": ["CRP", "CRP"],
            "Valeur_canonique": [10.0, 999.0],
            "flag_biologie_aberrante": [False, False],
        }
    )
    out = aggregate_biologie_pre_sortie(sejours, bio)
    assert out.loc[0, "bio_CRP_last"] == 10.0


def test_aggregate_pathologies_flags():
    patients = pd.DataFrame(
        {
            "PatientID": ["P1", "P2"],
            "PathologiesChroniques": [
                "Diabete|HTA|BPCO",
                "Aucune",
            ],
        }
    )
    out = aggregate_pathologies(patients)
    assert out.loc[0, "n_pathologies"] == 3
    assert out.loc[0, "patho_Diabete"] == 1
    assert out.loc[0, "patho_HTA"] == 1
    assert out.loc[1, "n_pathologies"] == 0
    assert out.loc[1, "patho_Diabete"] == 0


def test_aggregate_medications_atc_posologie():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "DateSortie": ["2024-01-10 12:00:00"],
        }
    )
    meds = pd.DataFrame(
        {
            "SejourID": ["S1", "S1", "S1"],
            "CodeATC": ["A10", "C07", "A10"],
            "Posologie": ["2 cp/j", "À la demande", "1 IV x3/j"],
            "DateDebut": ["2024-01-08", "2024-01-09", "2024-01-11"],
        }
    )
    out = aggregate_medications_detail(sejours, meds)
    # DateDebut post-sortie exclue → 2 lignes
    assert out.loc[0, "n_atc_distinct"] == 2
    assert out.loc[0, "atc_A10"] == 1
    assert out.loc[0, "atc_C07"] == 1
    assert out.loc[0, "posologie_a_demande"] == 1
    assert out.loc[0, "n_posologies_distinct"] == 2
