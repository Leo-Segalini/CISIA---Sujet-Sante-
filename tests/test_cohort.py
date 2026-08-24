import pandas as pd

from src.data.cohort import filter_domicile, patient_level_split


def test_filter_domicile_only():
    s = pd.DataFrame(
        {
            "SejourID": ["a", "b", "c"],
            "PatientID": ["p1", "p2", "p3"],
            "ModeSortie": ["Domicile", "Deces", "EHPAD"],
        }
    )
    out = filter_domicile(s)
    assert list(out["SejourID"]) == ["a"]


def test_patient_level_split_no_leakage():
    s = pd.DataFrame(
        {
            "SejourID": ["s1", "s2", "s3", "s4"],
            "PatientID": ["p1", "p1", "p2", "p3"],
            "ModeSortie": ["Domicile"] * 4,
        }
    )
    out = patient_level_split(s, seed=0)
    by_patient = out.groupby("PatientID")["split"].nunique()
    assert (by_patient == 1).all()
    assert set(out["split"]).issubset({"train", "val", "test"})
