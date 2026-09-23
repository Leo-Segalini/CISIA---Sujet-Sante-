from __future__ import annotations

import numpy as np
import pandas as pd

from src.model.reference import PrevalenceReference


def test_prevalence_reference_predicts_constant():
    ref = PrevalenceReference().fit(pd.DataFrame({"a": [1, 2]}), pd.Series([0, 1, 0, 1]))
    proba = ref.predict_proba(pd.DataFrame({"a": [3, 4]}))[:, 1]
    assert np.allclose(proba, 0.5)
