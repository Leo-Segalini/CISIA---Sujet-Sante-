from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.load import load_csv
from src.data.paths import ProjectPaths
from src.data.registry import CSV_FILES
from src.data.territoire import COMPLEMENT_COLUMNS, COMPLEMENT_NAME, complement_path

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
    "origine_donnee",
]

SENSITIVE = {"identite_directe", "sante_art9", "proxy_socio"}


def load_registre(path: Path | ProjectPaths) -> pd.DataFrame:
    """Charge le registre colonnes. Accepte un `Path` ou un `ProjectPaths`."""
    if isinstance(path, ProjectPaths):
        path = path.registres / "registre_colonnes.csv"
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
    registre: pd.DataFrame | ProjectPaths,
    column_index: pd.DataFrame | None = None,
) -> None:
    """Vérifie couverture registre ↔ CSV. Accepte `(reg, index)` ou `paths` seul."""
    if isinstance(registre, ProjectPaths):
        paths = registre
        registre = load_registre(paths)
        column_index = build_source_column_index(paths)
    if column_index is None:
        raise TypeError("column_index requis sauf si on passe un ProjectPaths")
    sujet = registre.loc[registre["fichier_source"].isin(CSV_FILES)]
    left = set(zip(sujet["fichier_source"], sujet["colonne"]))
    right = set(zip(column_index["fichier_source"], column_index["colonne"]))
    missing = sorted(right - left)
    extra = sorted(left - right)
    if missing or extra:
        raise AssertionError(
            f"Registre incomplet (sujet). Manquantes={missing} extra={extra}"
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
    if "origine_donnee" in registre.columns:
        bad_orig = registre.loc[
            ~registre["origine_donnee"].isin({"sujet", "insee_ajoute", "derive_affichage"})
        ]
        if len(bad_orig):
            raise AssertionError("origine_donnee inconnue")


def assert_complements_insee_enregistres(
    registre: pd.DataFrame, paths: ProjectPaths
) -> None:
    extra = complement_path(paths)
    if not extra.exists():
        return
    needed = {
        (COMPLEMENT_NAME, c)
        for c in COMPLEMENT_COLUMNS
        if c not in {"Commune", "CodePostal", "origine_ligne"}
    }
    have = set(zip(registre["fichier_source"], registre["colonne"]))
    missing = sorted(needed - have)
    if missing:
        raise AssertionError(f"Compléments INSEE absents du registre: {missing}")
