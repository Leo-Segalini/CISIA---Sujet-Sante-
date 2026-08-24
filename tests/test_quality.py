import pandas as pd

from src.data.quality import filter_objets_connectes_bons, recalculate_duree_sejour


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
