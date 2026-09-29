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

# Bornes absurdes (unité canonique) — au-delà = erreur de saisie / hallucination, pas une simple pathologie
BIO_ABSURD_RANGE: dict[str, tuple[float, float]] = {
    "Hemoglobine": (2.0, 25.0),  # g/dL ; 109 = confusion g/L
    "Creatinine": (10.0, 2000.0),  # µmol/L ; ~11 souvent mg/dL mal étiqueté
    "CRP": (0.0, 500.0),  # mg/L ; une CRP à 40 est pathologique mais plausible
    "Natremie": (100.0, 190.0),  # mmol/L ; 999 = hallucination
    "GlobulesBlancs": (0.1, 100.0),  # G/L
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
    """Marque les valeurs hors plage. Les NaN sont des trous, pas des aberrations."""
    out = df.copy()
    vals = pd.to_numeric(out[column], errors="coerce")
    out[flag_name] = vals.notna() & ((vals < low) | (vals > high))
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
    """Valeur + unité canonique ; flag les valeurs absurdes (pas les simples élévations cliniques)."""
    out = biologies.copy()
    out["Unite_canonique"] = out["Panel"].map(BIO_CANONICAL_UNIT)
    out["Valeur_canonique"] = pd.to_numeric(out["Valeur"], errors="coerce")
    bas = pd.to_numeric(out["ValeurReferenceBas"], errors="coerce")
    haut = pd.to_numeric(out["ValeurReferenceHaut"], errors="coerce")
    val = out["Valeur_canonique"]

    flags = pd.Series(False, index=out.index)
    # Négatif = toujours aberrant
    flags |= val.notna() & (val < 0)

    for panel, (lo, hi) in BIO_ABSURD_RANGE.items():
        mask = out["Panel"].eq(panel) & val.notna()
        flags |= mask & ((val < lo) | (val > hi))

    # Confusion d'unité / hors bornes très élargies (×0.5 / ×5), hors CRP (déjà bornée en absolu)
    non_crp = out["Panel"].ne("CRP") & val.notna() & bas.notna() & haut.notna()
    flags |= non_crp & ((val < bas * 0.5) | (val > haut * 5.0))

    out["flag_biologie_aberrante"] = flags
    return out
