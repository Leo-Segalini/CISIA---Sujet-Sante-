from __future__ import annotations

import numpy as np
import pandas as pd


def filter_domicile(sejours: pd.DataFrame) -> pd.DataFrame:
    if "ModeSortie" not in sejours.columns:
        raise KeyError("ModeSortie manquant")
    return sejours.loc[sejours["ModeSortie"] == "Domicile"].copy()


def patient_level_split(
    sejours: pd.DataFrame,
    *,
    seed: int = 42,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> pd.DataFrame:
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError("ratios must sum to 1")
    out = sejours.copy()
    patients = out["PatientID"].drop_duplicates().sort_values().to_numpy()
    rng = np.random.default_rng(seed)
    rng.shuffle(patients)
    n = len(patients)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    train = set(patients[:n_train])
    val = set(patients[n_train : n_train + n_val])

    def assign(pid: str) -> str:
        if pid in train:
            return "train"
        if pid in val:
            return "val"
        return "test"

    out["split"] = out["PatientID"].map(assign)
    return out
