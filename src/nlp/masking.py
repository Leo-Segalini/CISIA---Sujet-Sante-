from __future__ import annotations

import re

import pandas as pd

_TOKEN = "[PATIENT]"


def mask_text(text: str, names: list[str]) -> str:
    if not isinstance(text, str):
        return ""
    out = text
    for name in sorted({n.strip() for n in names if isinstance(n, str) and n.strip()}, key=len, reverse=True):
        out = re.sub(re.escape(name), _TOKEN, out, flags=re.IGNORECASE)
    # Motifs nominatifs fréquents restants
    out = re.sub(r"\b(Mme|M\.|Mr|Monsieur|Madame)\s+[A-ZÉÈÀ][\w'-]+", r"\1 " + _TOKEN, out)
    return out


def mask_comptes_rendus(
    comptes: pd.DataFrame, vault: pd.DataFrame, sejours: pd.DataFrame
) -> pd.DataFrame:
    patients = sejours[["SejourID", "PatientID"]].drop_duplicates()
    names = vault.merge(patients, on="PatientID", how="inner")
    by_sej: dict[str, list[str]] = {}
    for _, row in names.iterrows():
        by_sej.setdefault(row["SejourID"], [])
        for col in ("NomPrenom", "PersonneAPrevenir"):
            if col in row and pd.notna(row[col]):
                by_sej[row["SejourID"]].append(str(row[col]))
    out = comptes.copy()
    masked = []
    for _, row in out.iterrows():
        masked.append(mask_text(str(row.get("TexteCR", "")), by_sej.get(row["SejourID"], [])))
    out["TexteCR_masque"] = masked
    return out


def documents_par_sejour(comptes_masques: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        comptes_masques.groupby("SejourID")["TexteCR_masque"]
        .apply(lambda s: " ".join(x for x in s if isinstance(x, str)))
        .reset_index(name="document")
    )
    return grouped
