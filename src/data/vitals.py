"""Historique des constantes vitales — nettoyage et export pour l’UI."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.quality import PHYSIO_RANGES, flag_signes_vitaux

VITAL_ID_COLS = ("ConstanteID", "SejourID", "Horodatage")
VITAL_MEASURE_COLS = (
    "FrequenceCardiaque",
    "TensionSystolique",
    "TensionDiastolique",
    "Temperature",
    "FrequenceRespiratoire",
    "SpO2",
)
VITAL_DISPLAY_COLS = (*VITAL_ID_COLS, *VITAL_MEASURE_COLS)

_MOTIF_LABELS: dict[str, str] = {
    "FrequenceCardiaque": "Pouls hors plage",
    "TensionSystolique": "Tension systolique hors plage",
    "TensionDiastolique": "Tension diastolique hors plage",
    "Temperature": "Température hors plage",
    "FrequenceRespiratoire": "Respiration hors plage",
    "SpO2": "SpO₂ hors plage",
    "tension_incoherente": "Tension incohérente (diastole ≥ systole)",
}


def _plage_libelle(col: str) -> str:
    low, high = PHYSIO_RANGES[col]
    units = {
        "FrequenceCardiaque": "bpm",
        "TensionSystolique": "mmHg",
        "TensionDiastolique": "mmHg",
        "Temperature": "°C",
        "FrequenceRespiratoire": "/min",
        "SpO2": "%",
    }
    return f"{low:g}–{high:g} {units.get(col, '')}".strip()


def _motifs_ligne(row: pd.Series) -> list[str]:
    motifs: list[str] = []
    for col in VITAL_MEASURE_COLS:
        flag = f"flag_{col}_aberrant"
        if flag in row.index and bool(row[flag]):
            motifs.append(f"{_MOTIF_LABELS[col]} ({_plage_libelle(col)})")
    if bool(row.get("flag_tension_incoherente")):
        motifs.append(_MOTIF_LABELS["tension_incoherente"])
    return motifs


def enrich_signes_vitaux(signes: pd.DataFrame) -> pd.DataFrame:
    """Ajoute flags qualité, exclusion et motifs par ligne."""
    out = flag_signes_vitaux(signes.copy())
    out["Horodatage"] = pd.to_datetime(out["Horodatage"], errors="coerce")
    tas = pd.to_numeric(out["TensionSystolique"], errors="coerce")
    tad = pd.to_numeric(out["TensionDiastolique"], errors="coerce")
    out["flag_tension_incoherente"] = tas.notna() & tad.notna() & (tad >= tas)

    flag_cols = [c for c in out.columns if c.startswith("flag_")]
    out["exclue"] = out[flag_cols].any(axis=1)
    out["motifs_exclusion"] = out.apply(_motifs_ligne, axis=1)
    return out.sort_values(["SejourID", "Horodatage"], na_position="last")


def signes_valides(signes: pd.DataFrame) -> pd.DataFrame:
    """Mesures retenues après filtrage des valeurs impossibles ou incohérentes."""
    enriched = enrich_signes_vitaux(signes) if "exclue" not in signes.columns else signes
    return enriched.loc[~enriched["exclue"]].copy()


def _fmt_val(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_to_record(row: pd.Series) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "ConstanteID": str(row.get("ConstanteID", "")),
        "SejourID": str(row.get("SejourID", "")),
        "Horodatage": (
            row["Horodatage"].isoformat(sep=" ")
            if pd.notna(row.get("Horodatage"))
            else ""
        ),
        "exclue": bool(row.get("exclue")),
        "motifs_exclusion": list(row.get("motifs_exclusion") or []),
    }
    for col in VITAL_MEASURE_COLS:
        rec[col] = _fmt_val(row.get(col))
    return rec


def historique_constantes_sejour(signes: pd.DataFrame, sejour_id: str) -> dict[str, Any]:
    """Historique complet trié + synthèse du filtrage qualité."""
    # signes_view est déjà enrichi au chargement — ne pas rejouer le QC à chaque lit
    enriched = signes if "exclue" in signes.columns else enrich_signes_vitaux(signes)
    sub = enriched.loc[enriched["SejourID"].astype(str) == str(sejour_id)].copy()
    sub = sub.sort_values("Horodatage", ascending=False, na_position="last")
    mesures = [_row_to_record(row) for _, row in sub.iterrows()]
    retenues = [m for m in mesures if not m["exclue"]]
    exclues = [m for m in mesures if m["exclue"]]
    plages = {col: _plage_libelle(col) for col in VITAL_MEASURE_COLS}
    return {
        "total": len(mesures),
        "retenues": len(retenues),
        "exclues": len(exclues),
        "plages_reference": plages,
        "mesures": mesures,
        "mesures_retenues": retenues,
        "mesures_exclues": exclues,
    }


def index_dernieres_mesures(signes: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Dernière mesure retenue par séjour — lookup O(1) pour le plan d’étages."""
    enriched = signes if "exclue" in signes.columns else enrich_signes_vitaux(signes)
    if enriched.empty or "SejourID" not in enriched.columns:
        return {}
    ok = enriched.loc[~enriched["exclue"]].copy()
    if ok.empty:
        return {}
    ok["Horodatage"] = pd.to_datetime(ok["Horodatage"], errors="coerce")
    ok = ok.dropna(subset=["SejourID", "Horodatage"]).sort_values("Horodatage")
    out: dict[str, dict[str, Any]] = {}
    for sej, grp in ok.groupby(ok["SejourID"].astype(str), sort=False):
        last = grp.iloc[-1]
        snap: dict[str, Any] = {}
        for col in VITAL_MEASURE_COLS:
            v = last.get(col)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                try:
                    snap[col] = float(v)
                except (TypeError, ValueError):
                    continue
        if snap:
            out[str(sej)] = snap
    return out

