import pandas as pd

from src.data.features_sortie import aggregate_biologie_pre_sortie


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
