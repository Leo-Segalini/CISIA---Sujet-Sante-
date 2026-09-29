"""Exemples concrets de données incohérentes / hallucinées (démo pédagogique)."""

from __future__ import annotations

import pandas as pd

from src.data.load import load_csv
from src.data.paths import ProjectPaths
from src.data.quality import harmonize_biologie, recalculate_duree_sejour
from src.data.vitals import enrich_signes_vitaux


def collecter_exemples_hallucinations(paths: ProjectPaths) -> dict[str, pd.DataFrame]:
    """Retourne des échantillons de lignes problématiques par type d'anomalie."""
    exemples: dict[str, pd.DataFrame] = {}

    sejours = recalculate_duree_sejour(load_csv(paths, "sejours.csv", from_raw=False))
    inc = sejours.loc[sejours["flag_duree_incoherente"]]
    if len(inc):
        exemples["sejours_duree_incoherente"] = inc[
            ["SejourID", "DateAdmission", "DateSortie", "DureeSejour_brute", "DureeSejour"]
        ].head(12)

    sv = enrich_signes_vitaux(load_csv(paths, "signes_vitaux.csv", from_raw=False))
    excl = sv.loc[sv["exclue"]]
    if len(excl):
        cols = [
            "SejourID",
            "Horodatage",
            "FrequenceCardiaque",
            "TensionSystolique",
            "TensionDiastolique",
            "Temperature",
            "FrequenceRespiratoire",
            "SpO2",
            "motifs_exclusion",
        ]
        exemples["signes_vitaux_exclus"] = excl[[c for c in cols if c in excl.columns]].head(12)

    bio = harmonize_biologie(load_csv(paths, "biologies.csv", from_raw=False))
    ab = bio.loc[bio["flag_biologie_aberrante"]]
    if len(ab):
        exemples["biologies_aberrantes"] = ab[
            [
                "SejourID",
                "Panel",
                "Valeur",
                "ValeurReferenceBas",
                "ValeurReferenceHaut",
            ]
        ].head(12)

    oc = load_csv(paths, "objets_connectes.csv", from_raw=False)
    if "QualiteSignal" in oc.columns:
        mauvais = oc.loc[oc["QualiteSignal"] != "Bon"]
        if len(mauvais):
            exemples["objets_connectes_signal_faible"] = mauvais.head(12)

    actes = load_csv(paths, "actes.csv", from_raw=False)
    sj = sejours.set_index("SejourID")[["DateAdmission", "DateSortie"]]
    merged = actes.merge(sj, left_on="SejourID", right_index=True, how="left")
    dates = pd.to_datetime(merged["DateActe"], errors="coerce")
    adm = pd.to_datetime(merged["DateAdmission"], errors="coerce")
    sortie = pd.to_datetime(merged["DateSortie"], errors="coerce")
    # Comparaison au jour calendaire (DateActe est une date sans heure)
    d_day = dates.dt.normalize()
    a_day = adm.dt.normalize()
    s_day = sortie.dt.normalize()
    hors = merged.loc[dates.isna() | d_day.lt(a_day) | d_day.gt(s_day)]
    if len(hors):
        exemples["actes_date_hors_sejour"] = hors[
            ["ActeID", "SejourID", "DateActe", "DateAdmission", "DateSortie"]
        ].head(12)

    return exemples
