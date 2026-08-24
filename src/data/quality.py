from __future__ import annotations

import pandas as pd

PHYSIO_RANGES: dict[str, tuple[float, float]] = {
    "FrequenceCardiaque": (30, 220),
    "TensionSystolique": (60, 250),
    "TensionDiastolique": (30, 150),
    "Temperature": (34.0, 42.0),
    "FrequenceRespiratoire": (5, 60),
    "SpO2": (50, 100),
}

BIO_CANONICAL_UNIT = {
    "Hemoglobine": "g/dL",
    "Creatinine": "umol/L",
    "CRP": "mg/L",
    "Natremie": "mmol/L",
    "GlobulesBlancs": "G/L",
}


def recalculate_duree_sejour(sejours: pd.DataFrame) -> pd.DataFrame:
    out = sejours.copy()
    out["DureeSejour_brute"] = out["DureeSejour"]
    admission = pd.to_datetime(out["DateAdmission"], errors="coerce")
    sortie = pd.to_datetime(out["DateSortie"], errors="coerce")
    computed = (sortie - admission).dt.total_seconds() / 86400.0
    computed_days = computed.round().astype("Int64")
    brute = pd.to_numeric(out["DureeSejour_brute"], errors="coerce")
    incoherent = brute.isna() | (brute < 0) | ((brute - computed_days).abs() > 1)
    out["flag_duree_incoherente"] = incoherent.fillna(True)
    out["DureeSejour"] = brute.where(~out["flag_duree_incoherente"], computed_days)
    return out


def flag_out_of_range(
    df: pd.DataFrame, column: str, low: float, high: float, flag_name: str
) -> pd.DataFrame:
    out = df.copy()
    vals = pd.to_numeric(out[column], errors="coerce")
    out[flag_name] = vals.isna() | (vals < low) | (vals > high)
    return out


def flag_signes_vitaux(signes: pd.DataFrame) -> pd.DataFrame:
    out = signes.copy()
    for col, (low, high) in PHYSIO_RANGES.items():
        if col in out.columns:
            out = flag_out_of_range(out, col, low, high, f"flag_{col}_aberrant")
    return out


def filter_objets_connectes_bons(oc: pd.DataFrame) -> pd.DataFrame:
    return oc.loc[oc["QualiteSignal"] == "Bon"].copy()


def harmonize_biologie(biologies: pd.DataFrame) -> pd.DataFrame:
    """Valeur + unité canonique ; flag hors bornes élargies (×0.5 / ×2) ou NaN."""
    out = biologies.copy()
    out["Unite_canonique"] = out["Panel"].map(BIO_CANONICAL_UNIT)
    out["Valeur_canonique"] = pd.to_numeric(out["Valeur"], errors="coerce")
    bas = pd.to_numeric(out["ValeurReferenceBas"], errors="coerce")
    haut = pd.to_numeric(out["ValeurReferenceHaut"], errors="coerce")
    out["flag_biologie_aberrante"] = (
        out["Valeur_canonique"].isna()
        | (out["Valeur_canonique"] < bas * 0.5)
        | (out["Valeur_canonique"] > haut * 2.0)
    )
    return out
