import pandas as pd

from src.model.prepare import split_xy
from src.model.metrics import best_f2_threshold, classification_metrics


def test_split_xy_drops_ids_and_target():
    df = pd.DataFrame(
        {
            "SejourID": ["s1", "s2"],
            "PatientID": ["p1", "p2"],
            "split": ["train", "test"],
            "Readmission30j": [0, 1],
            "DureeSejour": [3, 5],
        }
    )
    X, y, split = split_xy(df)
    assert "SejourID" not in X.columns
    assert "Readmission30j" not in X.columns
    assert "split" not in X.columns
    assert list(y) == [0, 1]
    assert list(split) == ["train", "test"]


def test_best_f2_prefers_recall():
    y = [0, 0, 1, 1]
    # scores that catch both positives only at low threshold
    proba = [0.1, 0.2, 0.6, 0.7]
    t = best_f2_threshold(y, proba)
    m = classification_metrics(y, proba, t)
    assert m["recall"] >= 0.5
    assert "pr_auc" in m
