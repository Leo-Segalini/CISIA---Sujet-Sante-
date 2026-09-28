from __future__ import annotations

import pandas as pd

from src.data.quality import PHYSIO_RANGES, flag_signes_vitaux
from src.data.vitals import enrich_signes_vitaux


FORBIDDEN_COLUMNS = {"NomPrenom", "PersonneAPrevenir"}

# Tokens stables du sujet (hors « Aucune ») — flags binaires pour le score.
PATHOLOGIES_FLAGS = (
    "BPCO",
    "Diabete",
    "HTA",
    "InsuffisanceCardiaque",
    "InsuffisanceRenale",
    "Hyperlipidemie",
)

# Codes ATC présents dans medications.csv du sujet.
ATC_CODES = (
    "A02",
    "A10",
    "B01",
    "C01",
    "C03",
    "C07",
    "C09",
    "H02",
    "J01",
    "M01",
    "N02",
    "N05",
)


def compute_age_at_admission(patients: pd.DataFrame, sejours: pd.DataFrame) -> pd.Series:
    merged = sejours.merge(
        patients[["PatientID", "DateNaissance"]], on="PatientID", how="left"
    )
    admission = pd.to_datetime(merged["DateAdmission"], errors="coerce")
    birth = pd.to_datetime(merged["DateNaissance"], errors="coerce")
    age = (admission - birth).dt.days / 365.25
    return pd.Series(age.values, index=sejours.index, name="age_admission")


def aggregate_historique_12m(
    sejours: pd.DataFrame, historique: pd.DataFrame
) -> pd.DataFrame:
    hist = historique.copy()
    hist["DateEvenement"] = pd.to_datetime(hist["DateEvenement"], errors="coerce")
    rows = []
    for _, sej in sejours.iterrows():
        admission = pd.to_datetime(sej["DateAdmission"], errors="coerce")
        window_start = admission - pd.Timedelta(365, unit="D")
        sub = hist.loc[
            (hist["PatientID"] == sej["PatientID"])
            & (hist["DateEvenement"] >= window_start)
            & (hist["DateEvenement"] < admission)
        ]
        rows.append(
            {
                "SejourID": sej["SejourID"],
                "n_hosp_12m": int((sub["TypeEvenement"] == "Hospitalisation").sum()),
                "n_urg_12m": int((sub["TypeEvenement"] == "Urgence").sum()),
                "n_consult_12m": int((sub["TypeEvenement"] == "Consultation").sum()),
            }
        )
    return pd.DataFrame(rows)


def aggregate_biologie_pre_sortie(
    sejours: pd.DataFrame, biologies: pd.DataFrame
) -> pd.DataFrame:
    bio = biologies.copy()
    bio["DatePrelevement"] = pd.to_datetime(bio["DatePrelevement"], errors="coerce")
    if "flag_biologie_aberrante" not in bio.columns:
        bio["flag_biologie_aberrante"] = False
    if "Valeur_canonique" not in bio.columns:
        bio["Valeur_canonique"] = pd.to_numeric(bio.get("Valeur"), errors="coerce")

    panels = sorted(bio["Panel"].dropna().unique().tolist()) if "Panel" in bio.columns else []
    rows = []
    for _, sej in sejours.iterrows():
        sortie = pd.to_datetime(sej["DateSortie"], errors="coerce")
        sub = bio.loc[
            (bio["SejourID"] == sej["SejourID"])
            & (bio["DatePrelevement"] <= sortie)
            & (~bio["flag_biologie_aberrante"].fillna(False))
        ]
        rec: dict = {"SejourID": sej["SejourID"]}
        for panel in panels:
            col = f"bio_{panel}_last"
            panel_rows = sub.loc[sub["Panel"] == panel].sort_values("DatePrelevement")
            rec[col] = (
                float(panel_rows["Valeur_canonique"].iloc[-1])
                if len(panel_rows)
                else pd.NA
            )
        rows.append(rec)
    return pd.DataFrame(rows)


def aggregate_signes_vitaux_pre_sortie(
    sejours: pd.DataFrame, signes: pd.DataFrame
) -> pd.DataFrame:
    sv = enrich_signes_vitaux(signes)
    sv["Horodatage"] = pd.to_datetime(sv["Horodatage"], errors="coerce")
    measure_cols = [c for c in PHYSIO_RANGES if c in sv.columns]
    rows = []
    for _, sej in sejours.iterrows():
        sortie = pd.to_datetime(sej["DateSortie"], errors="coerce")
        sub = sv.loc[(sv["SejourID"] == sej["SejourID"]) & (sv["Horodatage"] <= sortie)]
        rec: dict = {"SejourID": sej["SejourID"]}
        for col in measure_cols:
            vals = pd.to_numeric(sub.loc[~sub["exclue"], col], errors="coerce")
            rec[f"sv_{col}_mean"] = float(vals.mean()) if vals.notna().any() else pd.NA
        rows.append(rec)
    return pd.DataFrame(rows)


def join_territoire(
    patients_pseudo: pd.DataFrame, territoire: pd.DataFrame
) -> pd.DataFrame:
    terr = territoire.copy()
    terr["CodePostal"] = terr["CodePostal"].astype(str)
    patients = patients_pseudo.copy()
    patients["CodePostal"] = patients["CodePostal"].astype(str)
    merged = patients.merge(
        terr,
        on=["Commune", "CodePostal"],
        how="left",
        indicator=True,
    )
    merged["territoire_inconnu"] = merged["_merge"] != "both"
    return merged.drop(columns=["_merge"])[
        [
            "PatientID",
            "IndiceDefavorisation",
            "DensiteMedicale",
            "PopulationCommune",
            "territoire_inconnu",
        ]
    ]


def _parse_pathologies(raw: object) -> set[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return set()
    parts = [p.strip() for p in str(raw).split("|") if p.strip()]
    return {p for p in parts if p and p != "Aucune"}


def aggregate_pathologies(patients_pseudo: pd.DataFrame) -> pd.DataFrame:
    """Encode PathologiesChroniques → compte + flags (analyse retour patient)."""
    if "PathologiesChroniques" not in patients_pseudo.columns:
        raise KeyError("PathologiesChroniques manquant dans patients_pseudo")
    rows = []
    for _, row in patients_pseudo.iterrows():
        tokens = _parse_pathologies(row["PathologiesChroniques"])
        rec: dict = {
            "PatientID": row["PatientID"],
            "n_pathologies": len(tokens),
        }
        for name in PATHOLOGIES_FLAGS:
            rec[f"patho_{name}"] = int(name in tokens)
        rows.append(rec)
    return pd.DataFrame(rows)


def aggregate_medications_detail(
    sejours: pd.DataFrame, medications: pd.DataFrame
) -> pd.DataFrame:
    """ATC + posologie (séjour) — complète n_meds / n_voies pour l'entraînement."""
    meds = medications.copy()
    if "DateDebut" in meds.columns:
        meds["DateDebut"] = pd.to_datetime(meds["DateDebut"], errors="coerce")
    rows = []
    for _, sej in sejours.iterrows():
        sortie = pd.to_datetime(sej["DateSortie"], errors="coerce")
        sub = meds.loc[meds["SejourID"] == sej["SejourID"]].copy()
        if "DateDebut" in sub.columns and pd.notna(sortie):
            sub = sub.loc[sub["DateDebut"].isna() | (sub["DateDebut"] <= sortie)]
        atc = sub["CodeATC"].dropna().astype(str) if "CodeATC" in sub.columns else pd.Series(dtype=str)
        poso = (
            sub["Posologie"].dropna().astype(str)
            if "Posologie" in sub.columns
            else pd.Series(dtype=str)
        )
        rec: dict = {
            "SejourID": sej["SejourID"],
            "n_atc_distinct": int(atc.nunique()),
            "n_posologies_distinct": int(poso.nunique()),
            "posologie_a_demande": int(
                any("demande" in p.casefold() for p in poso.tolist())
            ),
        }
        atc_set = set(atc.tolist())
        for code in ATC_CODES:
            rec[f"atc_{code}"] = int(code in atc_set)
        rows.append(rec)
    return pd.DataFrame(rows)


def _count_pre_sortie(
    sejours: pd.DataFrame,
    events: pd.DataFrame,
    date_col: str,
    out_col: str,
) -> pd.DataFrame:
    ev = events.copy()
    ev[date_col] = pd.to_datetime(ev[date_col], errors="coerce")
    rows = []
    for _, sej in sejours.iterrows():
        sortie = pd.to_datetime(sej["DateSortie"], errors="coerce")
        n = int(
            (
                (ev["SejourID"] == sej["SejourID"]) & (ev[date_col] <= sortie)
            ).sum()
        )
        rows.append({"SejourID": sej["SejourID"], out_col: n})
    return pd.DataFrame(rows)


def build_features_score_sortie(
    sejours: pd.DataFrame,
    patients_pseudo: pd.DataFrame,
    historique: pd.DataFrame,
    biologies: pd.DataFrame,
    signes: pd.DataFrame,
    diagnostics: pd.DataFrame,
    actes: pd.DataFrame,
    medications: pd.DataFrame,
    territoire: pd.DataFrame,
) -> pd.DataFrame:
    base = sejours.copy()
    base["age_admission"] = compute_age_at_admission(patients_pseudo, base)
    sexe = patients_pseudo[["PatientID", "Sexe"]]
    base = base.merge(sexe, on="PatientID", how="left")

    hist_agg = aggregate_historique_12m(base, historique)
    bio_agg = aggregate_biologie_pre_sortie(base, biologies)
    sv_agg = aggregate_signes_vitaux_pre_sortie(base, signes)
    n_actes = _count_pre_sortie(base, actes, "DateActe", "n_actes")

    diag = diagnostics.copy()
    diag_n = (
        diag.groupby("SejourID")
        .agg(
            n_diag=("DiagnosticID", "count"),
            n_diag_principal=("Role", lambda s: int((s == "Principal").sum())),
        )
        .reset_index()
    )

    meds = medications.copy()
    med_n = (
        meds.groupby("SejourID")
        .agg(
            n_meds=("PrescriptionID", "count"),
            n_voies=("Voie", "nunique"),
        )
        .reset_index()
    )
    med_detail = aggregate_medications_detail(base, medications)
    patho = aggregate_pathologies(patients_pseudo)

    terr = join_territoire(patients_pseudo, territoire)

    out = base.merge(hist_agg, on="SejourID", how="left")
    out = out.merge(bio_agg, on="SejourID", how="left")
    out = out.merge(sv_agg, on="SejourID", how="left")
    out = out.merge(n_actes, on="SejourID", how="left")
    out = out.merge(diag_n, on="SejourID", how="left")
    out = out.merge(med_n, on="SejourID", how="left")
    out = out.merge(med_detail, on="SejourID", how="left")
    out = out.merge(patho, on="PatientID", how="left")
    out = out.merge(terr, on="PatientID", how="left")

    keep = [
        "SejourID",
        "PatientID",
        "split",
        "Readmission30j",
        "DureeSejour",
        "Service",
        "TypeSejour",
        "GHM",
        "age_admission",
        "Sexe",
        "n_hosp_12m",
        "n_urg_12m",
        "n_consult_12m",
        "n_actes",
        "n_diag",
        "n_diag_principal",
        "n_meds",
        "n_voies",
        "n_atc_distinct",
        "n_posologies_distinct",
        "posologie_a_demande",
        "n_pathologies",
        "IndiceDefavorisation",
        "DensiteMedicale",
        "PopulationCommune",
        "territoire_inconnu",
    ]
    extra = [
        c
        for c in out.columns
        if c.startswith("bio_")
        or c.startswith("sv_")
        or c.startswith("patho_")
        or c.startswith("atc_")
    ]
    out = out[keep + sorted(extra)]
    if not FORBIDDEN_COLUMNS.isdisjoint(out.columns):
        raise AssertionError("Nominatif présent dans les features sortie")
    if any(c.startswith("oc_") for c in out.columns):
        raise AssertionError("Objets connectés présents dans le score sortie")
    return out
