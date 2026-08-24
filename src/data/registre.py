from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.load import load_csv
from src.data.paths import CSV_FILES, ProjectPaths

REGISTRE_COLUMNS = [
    "fichier_source",
    "colonne",
    "grain",
    "categorie",
    "sensibilite",
    "usage_score_sortie",
    "usage_score_tele",
    "justification_hopital",
    "risque_principal",
    "regle_nettoyage",
]

SENSITIVE = {"identite_directe", "sante_art9", "proxy_socio"}


def load_registre(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Registre introuvable: {path}")
    df = pd.read_csv(path)
    missing = [c for c in REGISTRE_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Colonnes registre absentes: {missing}")
    return df


def build_source_column_index(paths: ProjectPaths) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for name in CSV_FILES:
        df = load_csv(paths, name, from_raw=False)
        for col in df.columns:
            rows.append({"fichier_source": name, "colonne": col})
    return pd.DataFrame(rows)


def assert_registre_covers_sources(
    registre: pd.DataFrame, column_index: pd.DataFrame
) -> None:
    left = set(zip(registre["fichier_source"], registre["colonne"]))
    right = set(zip(column_index["fichier_source"], column_index["colonne"]))
    missing = sorted(right - left)
    extra = sorted(left - right)
    if missing or extra:
        raise AssertionError(
            f"Registre incomplet. Manquantes={missing} extra={extra}"
        )


def assert_justifications(registre: pd.DataFrame) -> None:
    mask = registre["usage_score_sortie"].eq("autorise") | registre[
        "usage_score_tele"
    ].eq("autorise")
    mask &= registre["sensibilite"].isin(SENSITIVE)
    justif = registre["justification_hopital"].fillna("").astype(str).str.strip()
    bad = registre.loc[mask & justif.eq("")]
    if len(bad):
        raise AssertionError(
            "Justifications manquantes:\n"
            + bad[["fichier_source", "colonne"]].to_string(index=False)
        )
