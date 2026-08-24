from __future__ import annotations

import pandas as pd

from src.data.paths import IDENTITY_COLUMNS, ProjectPaths


def split_identity_and_pseudonymise(
    patients: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [c for c in IDENTITY_COLUMNS if c not in patients.columns]
    if missing:
        raise KeyError(f"Colonnes identité absentes: {missing}")
    if "PatientID" not in patients.columns:
        raise KeyError("PatientID manquant")
    vault = patients[["PatientID", *IDENTITY_COLUMNS]].copy()
    pseudo = patients.drop(columns=list(IDENTITY_COLUMNS)).copy()
    return vault, pseudo


def persist_identity_split(
    paths: ProjectPaths,
    vault: pd.DataFrame,
    patients_pseudo: pd.DataFrame,
) -> None:
    paths.ensure_data_dirs()
    vault.to_csv(paths.vault / "patients_identite.csv", index=False)
    patients_pseudo.to_csv(paths.pseudonymise / "patients.csv", index=False)
