"""
Analyse données pour CISIA — synthèse jury / gouvernance.

Couvre : cohorte (exclusion décès), nulls & sentinelles, cohérence temporelle,
pathologies ↔ réadmission.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.cohort import filter_domicile
from src.data.load import load_csv
from src.data.paths import ProjectPaths
from src.data.quality import recalculate_duree_sejour
from src.data.quality_report import (
    aberrant_rates,
    dates_hors_sejour,
    mal_note_rates,
    missing_rates,
)
from src.data.registry import CSV_FILES, list_sources

# Codes / placeholders fréquents pour « valeur sentinelle » (manquante codée)
SENTINEL_NUM = {-1, -9, -99, -999, 88, 99, 999, 9999}
SENTINEL_STR = {
    "",
    "na",
    "n/a",
    "null",
    "none",
    "nan",
    "?",
    ".",
    "-",
    "nd",
    "nc",
    "inconnu",
}


def _is_null_series(s: pd.Series) -> pd.Series:
    if s.dtype == object or pd.api.types.is_string_dtype(s):
        return s.isna() | s.astype(str).str.strip().eq("")
    return s.isna()


def _is_sentinel_series(s: pd.Series) -> pd.Series:
    """True si valeur sentinelle (hors null classique)."""
    nulls = _is_null_series(s)
    if pd.api.types.is_numeric_dtype(s):
        nums = pd.to_numeric(s, errors="coerce")
        return (~nulls) & nums.isin(list(SENTINEL_NUM))
    text = s.astype(str).str.strip().str.lower()
    return (~nulls) & text.isin(SENTINEL_STR)


def nulls_and_sentinels_table(df: pd.DataFrame, fichier: str) -> list[dict[str, Any]]:
    """Par colonne : nulls + sentinelles (comptes et %)."""
    n = max(len(df), 1)
    rows: list[dict[str, Any]] = []
    for col in df.columns:
        null_mask = _is_null_series(df[col])
        sent_mask = _is_sentinel_series(df[col])
        n_null = int(null_mask.sum())
        n_sent = int(sent_mask.sum())
        rows.append(
            {
                "fichier": fichier,
                "colonne": col,
                "n_lignes": int(len(df)),
                "n_null": n_null,
                "pct_null": round(100.0 * n_null / n, 2),
                "n_sentinelle": n_sent,
                "pct_sentinelle": round(100.0 * n_sent / n, 2),
            }
        )
    return rows


def _event_date_mapping() -> dict[str, str]:
    return {
        "actes.csv": "DateActe",
        "medications.csv": "DateDebut",
        "comptes_rendus.csv": "DateCR",
        "biologies.csv": "DatePrelevement",
        "signes_vitaux.csv": "Horodatage",
        "historique.csv": "DateEvenement",
    }


def temporal_coherence_report(
    paths: ProjectPaths, sejours: pd.DataFrame
) -> dict[str, Any]:
    """Point complet sur la logique des dates (séjours + événements liés)."""
    sj = recalculate_duree_sejour(sejours)
    adm = pd.to_datetime(sj["DateAdmission"], errors="coerce")
    sortie = pd.to_datetime(sj["DateSortie"], errors="coerce")
    sejour_checks = {
        "n_sejours": int(len(sj)),
        "admission_manquante": int(adm.isna().sum()),
        "sortie_manquante": int(sortie.isna().sum()),
        "sortie_avant_admission": int((sortie < adm).fillna(False).sum()),
        "duree_incoherente": int(sj["flag_duree_incoherente"].fillna(False).sum()),
        "pct_duree_incoherente": round(
            100.0 * float(sj["flag_duree_incoherente"].mean()), 2
        ),
    }

    events: list[dict[str, Any]] = []
    mapping = _event_date_mapping()
    for name, date_col in mapping.items():
        try:
            df = load_csv(paths, name, from_raw=False)
        except FileNotFoundError:
            continue
        if date_col not in df.columns:
            continue
        if name == "historique.csv":
            # lié au patient, pas au séjour courant — on signale seulement dates vides
            dates = pd.to_datetime(df[date_col], errors="coerce")
            events.append(
                {
                    "fichier": name,
                    "colonne_date": date_col,
                    "n_lignes": int(len(df)),
                    "n_date_invalide": int(dates.isna().sum()),
                    "n_hors_fenetre_sejour": None,
                    "pct_hors_fenetre_sejour": None,
                    "note": "Historique patient (hors fenêtre séjour courant)",
                }
            )
            continue
        if "SejourID" not in df.columns:
            continue
        hors = dates_hors_sejour(df, sj, date_col=date_col)
        # Comparaison au jour près pour le diagnostic pédagogique
        ref = sj.set_index("SejourID")[["DateAdmission", "DateSortie"]]
        merged = df.merge(ref, left_on="SejourID", right_index=True, how="left")
        d = pd.to_datetime(merged[date_col], errors="coerce").dt.normalize()
        a = pd.to_datetime(merged["DateAdmission"], errors="coerce").dt.normalize()
        s = pd.to_datetime(merged["DateSortie"], errors="coerce").dt.normalize()
        avant = int((d < a).fillna(False).sum())
        apres = int((d > s).fillna(False).sum())
        events.append(
            {
                "fichier": name,
                "colonne_date": date_col,
                "n_lignes": int(len(df)),
                "n_date_invalide": int(d.isna().sum()),
                "n_hors_fenetre_sejour": int(hors.sum()),
                "pct_hors_fenetre_sejour": round(100.0 * float(hors.mean()), 2),
                "n_avant_admission": avant,
                "n_apres_sortie": apres,
                "note": "Horodatage hors [admission, sortie] = incohérence / hallucination date",
            }
        )

    return {"sejours": sejour_checks, "evenements": events}


def cohort_training_summary(sejours: pd.DataFrame) -> dict[str, Any]:
    """Rappel : les décès (et hors domicile) sont exclus de l’entraînement."""
    counts = (
        sejours["ModeSortie"].astype(str).value_counts(dropna=False).to_dict()
        if "ModeSortie" in sejours.columns
        else {}
    )
    eligibles = filter_domicile(sejours)
    return {
        "regle": "ModeSortie == Domicile uniquement (Deces, Transfert, EHPAD, HAD exclus)",
        "n_sejours_bruts": int(len(sejours)),
        "n_eligibles_entrainement": int(len(eligibles)),
        "n_exclus": int(len(sejours) - len(eligibles)),
        "repartition_mode_sortie": {str(k): int(v) for k, v in counts.items()},
        "n_deces_exclus": int(counts.get("Deces", 0)),
    }


def pathologies_readmission(paths: ProjectPaths) -> list[dict[str, Any]]:
    """Maladies chroniques associées au plus fort taux de retour 30 j."""
    parquet = paths.curated / "features_score_sortie.parquet"
    if not parquet.exists():
        return []
    df = pd.read_parquet(parquet)
    if "Readmission30j" not in df.columns:
        return []
    rows: list[dict[str, Any]] = []
    patho_cols = sorted(c for c in df.columns if c.startswith("patho_"))
    base_rate = float(df["Readmission30j"].mean())
    for col in patho_cols:
        mask = df[col].fillna(0).astype(int).eq(1)
        n = int(mask.sum())
        if n == 0:
            continue
        rate = float(df.loc[mask, "Readmission30j"].mean())
        rows.append(
            {
                "pathologie": col.replace("patho_", ""),
                "n_sejours": n,
                "taux_readmission_30j": round(rate, 4),
                "pct_readmission": round(100.0 * rate, 1),
                "pct_vs_global": round(100.0 * (rate - base_rate), 1),
            }
        )
    rows.sort(key=lambda r: r["taux_readmission_30j"], reverse=True)
    if "n_pathologies" in df.columns:
        corr = float(df[["n_pathologies", "Readmission30j"]].corr().iloc[0, 1])
    else:
        corr = None
    for r in rows:
        r["correlation_n_pathologies"] = (
            round(corr, 3) if corr is not None and corr == corr else None
        )
    return rows


def _counts_from_rates(rates: dict[str, float], n_lignes: int) -> dict[str, int]:
    """Convertit des taux (0–1) en effectifs arrondis."""
    return {k: int(round(float(v) * n_lignes)) for k, v in rates.items()}


def build_stats_qualite(
    cohorte: dict[str, Any],
    resume_fichiers: list[dict[str, Any]],
    temporalite: dict[str, Any],
) -> dict[str, Any]:
    """Synthèse graphique : exclus / hallucinations / incohérences."""
    n_aberrants = 0
    n_mal_notes = 0
    detail_fichiers: list[dict[str, Any]] = []
    for f in resume_fichiers:
        n = int(f["n_lignes"])
        aberr_c = _counts_from_rates(f.get("flags_aberrants") or {}, n)
        mal_c = _counts_from_rates(f.get("flags_mal_notes") or {}, n)
        n_ab = sum(aberr_c.values())
        n_mal = sum(mal_c.values())
        n_aberrants += n_ab
        n_mal_notes += n_mal
        detail_fichiers.append(
            {
                "fichier": f["fichier"],
                "libelle": f["libelle"],
                "n_aberrants": n_ab,
                "n_mal_notes": n_mal,
                "n_null": int(f.get("n_null_total") or 0),
                "n_sentinelle": int(f.get("n_sentinelle_total") or 0),
            }
        )

    n_dates_hors = 0
    for e in temporalite.get("evenements") or []:
        n_dates_hors += int(e.get("n_hors_fenetre_sejour") or 0)
    sej = temporalite.get("sejours") or {}
    n_duree = int(sej.get("duree_incoherente") or 0)
    n_sortie_avant = int(sej.get("sortie_avant_admission") or 0)
    n_incoherences = n_dates_hors + n_duree + n_sortie_avant

    categories = [
        {
            "id": "exclus",
            "label": "Exclus de l’entraînement",
            "n": int(cohorte.get("n_exclus") or 0),
            "detail": f"dont {cohorte.get('n_deces_exclus', 0)} décès",
        },
        {
            "id": "hallucinations",
            "label": "Hallucinations / mal notés",
            "n": n_mal_notes,
            "detail": "incohérences métier (durée, tension, dates hors séjour…)",
        },
        {
            "id": "aberrants",
            "label": "Valeurs aberrantes",
            "n": n_aberrants,
            "detail": "hors plage physiologique / biologique",
        },
        {
            "id": "incoherences",
            "label": "Incohérences temporelles",
            "n": n_incoherences,
            "detail": f"{n_dates_hors} dates hors séjour + {n_duree} durées + {n_sortie_avant} sorties avant adm.",
        },
    ]
    return {
        "categories": categories,
        "par_fichier": detail_fichiers,
        "n_dates_hors_sejour": n_dates_hors,
        "n_duree_incoherente": n_duree,
    }


def build_analyse_complete(paths: ProjectPaths) -> dict[str, Any]:
    """Payload unique pour la page CISIA / Jupyter."""
    sejours = load_csv(paths, "sejours.csv", from_raw=False)
    null_sentinel_rows: list[dict[str, Any]] = []
    resume_fichiers: list[dict[str, Any]] = []

    for spec in list_sources(required_only=True):
        name = spec.filename
        df = load_csv(paths, name, from_raw=False)
        detail = nulls_and_sentinels_table(df, name)
        null_sentinel_rows.extend(detail)
        n_null = sum(r["n_null"] for r in detail)
        n_sent = sum(r["n_sentinelle"] for r in detail)
        aberr = aberrant_rates(name, df)
        mal = mal_note_rates(name, df, sejours=sejours)
        n = int(len(df))
        resume_fichiers.append(
            {
                "fichier": name,
                "libelle": spec.label,
                "n_lignes": n,
                "n_colonnes": int(df.shape[1]),
                "n_null_total": n_null,
                "n_sentinelle_total": n_sent,
                "pct_null_moyen": round(
                    100.0 * sum(missing_rates(df).values()) / max(len(df.columns), 1),
                    2,
                ),
                "flags_aberrants": {k: round(v, 4) for k, v in aberr.items()},
                "flags_mal_notes": {k: round(v, 4) for k, v in mal.items()},
                "counts_aberrants": _counts_from_rates(aberr, n),
                "counts_mal_notes": _counts_from_rates(mal, n),
            }
        )

    cohorte = cohort_training_summary(sejours)
    temporalite = temporal_coherence_report(paths, sejours)
    stats_qualite = build_stats_qualite(cohorte, resume_fichiers, temporalite)

    return {
        "cohorte": cohorte,
        "nulls_sentinelles": null_sentinel_rows,
        "resume_fichiers": resume_fichiers,
        "temporalite": temporalite,
        "pathologies_readmission": pathologies_readmission(paths),
        "stats_qualite": stats_qualite,
        "sources": [s.filename for s in list_sources(required_only=True)],
        "sentinelles_reference": {
            "numeriques": sorted(SENTINEL_NUM),
            "textes": sorted(SENTINEL_STR),
        },
    }
