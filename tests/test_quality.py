import pandas as pd

from src.data.quality import (
    flag_out_of_range,
    filter_objets_connectes_bons,
    harmonize_biologie,
    recalculate_duree_sejour,
)


def test_recalculate_negative_duree():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "DateAdmission": ["2024-01-10 10:00:00"],
            "DateSortie": ["2024-01-12 10:00:00"],
            "DureeSejour": [-3],
        }
    )
    out = recalculate_duree_sejour(sejours)
    assert out.loc[0, "DureeSejour_brute"] == -3
    assert out.loc[0, "DureeSejour"] == 2
    assert bool(out.loc[0, "flag_duree_incoherente"]) is True


def test_objets_connectes_bons_only():
    oc = pd.DataFrame(
        {
            "MesureID": [1, 2, 3],
            "QualiteSignal": ["Bon", "Gap", "CapteurDefaillant"],
            "Valeur": [1.0, 2.0, 3.0],
        }
    )
    out = filter_objets_connectes_bons(oc)
    assert len(out) == 1
    assert out.iloc[0]["QualiteSignal"] == "Bon"


def test_nan_n_est_pas_aberrant():
    df = pd.DataFrame({"FrequenceCardiaque": [80.0, None, 5.0]})
    out = flag_out_of_range(df, "FrequenceCardiaque", 30, 220, "flag")
    assert bool(out.loc[0, "flag"]) is False
    assert bool(out.loc[1, "flag"]) is False  # trou ≠ aberration
    assert bool(out.loc[2, "flag"]) is True


def test_biologie_crp_elevee_pas_aberrante_mais_negative_oui():
    bio = pd.DataFrame(
        {
            "Panel": ["CRP", "CRP", "Natremie", "Hemoglobine"],
            "Valeur": [43.0, -5.0, 999.0, 109.0],
            "ValeurReferenceBas": [0, 0, 135, 12],
            "ValeurReferenceHaut": [5, 5, 145, 16],
        }
    )
    out = harmonize_biologie(bio)
    assert bool(out.loc[0, "flag_biologie_aberrante"]) is False  # CRP 43 plausible
    assert bool(out.loc[1, "flag_biologie_aberrante"]) is True
    assert bool(out.loc[2, "flag_biologie_aberrante"]) is True
    assert bool(out.loc[3, "flag_biologie_aberrante"]) is True
