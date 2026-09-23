from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingClassifier

from src.model.train import CategoryToCode


def shap_top_features(
    coder: CategoryToCode,
    clf: HistGradientBoostingClassifier,
    X: pd.DataFrame,
    *,
    max_rows: int = 80,
) -> pd.DataFrame:
    sample = coder.transform(X.head(max_rows))
    explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(sample)
    if isinstance(values, list):
        values = values[1]
    mean_abs = np.abs(np.asarray(values)).mean(axis=0)
    return (
        pd.DataFrame({"feature": sample.columns, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
