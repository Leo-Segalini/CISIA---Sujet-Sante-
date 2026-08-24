import pandas as pd

from src.data.features_tele import aggregate_objets_fenetre_fixe


def test_fenetre_fixe_7j():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "PatientID": ["P1"],
            "DateSortie": ["2024-01-01 00:00:00"],
        }
    )
    oc = pd.DataFrame(
        {
            "PatientID": ["P1", "P1", "P1"],
            "Horodatage": [
                "2024-01-01 12:00:00",
                "2024-01-05 12:00:00",
                "2024-01-10 12:00:00",
            ],
            "TypeMesure": ["SpO2", "SpO2", "SpO2"],
            "Valeur": [95.0, 97.0, 80.0],
            "QualiteSignal": ["Bon", "Bon", "Bon"],
        }
    )
    out = aggregate_objets_fenetre_fixe(sejours, oc, horizon_jours=7)
    assert out.loc[0, "oc_SpO2_n"] == 2
    assert abs(out.loc[0, "oc_SpO2_mean"] - 96.0) < 1e-9
