from __future__ import annotations

import pandas as pd


def aggregate_objets_fenetre_fixe(
    sejours: pd.DataFrame,
    objets: pd.DataFrame,
    *,
    horizon_jours: int = 7,
) -> pd.DataFrame:
    oc = objets.copy()
    oc["Horodatage"] = pd.to_datetime(oc["Horodatage"], errors="coerce")
    types = sorted(oc["TypeMesure"].dropna().unique().tolist()) if "TypeMesure" in oc.columns else []
    rows = []
    for _, sej in sejours.iterrows():
        sortie = pd.to_datetime(sej["DateSortie"], errors="coerce")
        fin = sortie + pd.Timedelta(int(horizon_jours), unit="D")
        sub = oc.loc[
            (oc["PatientID"] == sej["PatientID"])
            & (oc["Horodatage"] > sortie)
            & (oc["Horodatage"] <= fin)
        ]
        rec: dict = {"SejourID": sej["SejourID"]}
        days = sub["Horodatage"].dt.normalize().nunique() if len(sub) else 0
        rec["oc_coverage_days"] = int(days)
        for t in types:
            vals = pd.to_numeric(sub.loc[sub["TypeMesure"] == t, "Valeur"], errors="coerce")
            rec[f"oc_{t}_n"] = int(vals.notna().sum())
            rec[f"oc_{t}_mean"] = float(vals.mean()) if vals.notna().any() else pd.NA
        rows.append(rec)
    return pd.DataFrame(rows)


def build_features_score_tele(
    features_sortie: pd.DataFrame,
    sejours: pd.DataFrame,
    objets_bons: pd.DataFrame,
    *,
    horizon_jours: int = 7,
) -> pd.DataFrame:
    oc_agg = aggregate_objets_fenetre_fixe(
        sejours, objets_bons, horizon_jours=horizon_jours
    )
    out = features_sortie.merge(oc_agg, on="SejourID", how="left")
    if "NomPrenom" in out.columns or "PersonneAPrevenir" in out.columns:
        raise AssertionError("Nominatif présent dans les features télé")
    return out
