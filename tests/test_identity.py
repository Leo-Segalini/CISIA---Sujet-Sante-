import pandas as pd

from src.data.identity import persist_identity_split, split_identity_and_pseudonymise
from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root


def test_split_moves_identity_columns():
    patients = pd.DataFrame(
        {
            "PatientID": ["PAT-1"],
            "NomPrenom": ["Dupont Alice"],
            "PersonneAPrevenir": ["Fils"],
            "Sexe": ["F"],
            "CodePostal": ["75001"],
        }
    )
    vault, pseudo = split_identity_and_pseudonymise(patients)
    assert list(vault.columns) == ["PatientID", "NomPrenom", "PersonneAPrevenir"]
    assert "NomPrenom" not in pseudo.columns
    assert "PersonneAPrevenir" not in pseudo.columns
    assert pseudo.loc[0, "Sexe"] == "F"


def test_copy_and_persist_real_sources(tmp_path):
    root = get_project_root()
    tp = ProjectPaths(root=tmp_path)
    patients = load_csv(ProjectPaths(root=root), "patients.csv", from_raw=False)
    vault, pseudo = split_identity_and_pseudonymise(patients)
    persist_identity_split(tp, vault, pseudo)
    assert (tp.vault / "patients_identite.csv").exists()
    reloaded = pd.read_csv(tp.pseudonymise / "patients.csv")
    assert "NomPrenom" not in reloaded.columns
