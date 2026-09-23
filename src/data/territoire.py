from __future__ import annotations

import pandas as pd

from src.data.insee_lookup import INSEE_PAR_COMMUNE, MILLESIME
from src.data.paths import ProjectPaths

COMPLEMENT_NAME = "territoire_insee_complements.csv"
COMPLEMENT_COLUMNS = [
    "Commune",
    "CodePostal",
    "INSEE_ajoute_CodeCommune",
    "INSEE_ajoute_PopulationLegale",
    "INSEE_ajoute_PartPlus65Ans_pct",
    "INSEE_ajoute_Departement",
    "INSEE_ajoute_Region",
    "INSEE_ajoute_EcartPop_vs_sujet",
    "INSEE_ajoute_Millesime",
    "origine_ligne",
]


def complement_path(paths: ProjectPaths):
    return paths.root / "data" / "external" / COMPLEMENT_NAME


def build_complements_from_sujet(territoire_sujet: pd.DataFrame) -> pd.DataFrame:
    """Construit le fichier INSEE ajouté sans modifier le CSV du sujet."""
    rows = []
    for rec in territoire_sujet.to_dict(orient="records"):
        commune = str(rec["Commune"])
        cp = str(rec["CodePostal"])
        pop_sujet = pd.to_numeric(rec.get("PopulationCommune"), errors="coerce")
        meta = INSEE_PAR_COMMUNE.get((commune, cp))
        if meta is None:
            rows.append(
                {
                    "Commune": commune,
                    "CodePostal": cp,
                    "INSEE_ajoute_CodeCommune": pd.NA,
                    "INSEE_ajoute_PopulationLegale": pd.NA,
                    "INSEE_ajoute_PartPlus65Ans_pct": pd.NA,
                    "INSEE_ajoute_Departement": pd.NA,
                    "INSEE_ajoute_Region": pd.NA,
                    "INSEE_ajoute_EcartPop_vs_sujet": pd.NA,
                    "INSEE_ajoute_Millesime": MILLESIME,
                    "origine_ligne": "insee_ajoute",
                }
            )
            continue
        cog, pop_insee, p65, dept, region = meta
        ecart = (
            int(pop_sujet) - pop_insee if pd.notna(pop_sujet) else pd.NA
        )
        rows.append(
            {
                "Commune": commune,
                "CodePostal": cp,
                "INSEE_ajoute_CodeCommune": cog,
                "INSEE_ajoute_PopulationLegale": pop_insee,
                "INSEE_ajoute_PartPlus65Ans_pct": p65,
                "INSEE_ajoute_Departement": dept,
                "INSEE_ajoute_Region": region,
                "INSEE_ajoute_EcartPop_vs_sujet": ecart,
                "INSEE_ajoute_Millesime": MILLESIME,
                "origine_ligne": "insee_ajoute",
            }
        )
    return pd.DataFrame(rows, columns=COMPLEMENT_COLUMNS)


def write_complements(paths: ProjectPaths, territoire_sujet: pd.DataFrame) -> None:
    dest = complement_path(paths)
    dest.parent.mkdir(parents=True, exist_ok=True)
    build_complements_from_sujet(territoire_sujet).to_csv(dest, index=False)


def load_territoire_enrichi(paths: ProjectPaths, territoire_sujet: pd.DataFrame) -> pd.DataFrame:
    """Sujet inchangé + colonnes INSEE préfixées INSEE_ajoute_*."""
    base = territoire_sujet.copy()
    base["CodePostal"] = base["CodePostal"].astype(str)
    extra = complement_path(paths)
    if not extra.exists():
        return base
    comp = pd.read_csv(extra, dtype={"CodePostal": str, "INSEE_ajoute_CodeCommune": str})
    merged = base.merge(comp, on=["Commune", "CodePostal"], how="left")
    return merged
