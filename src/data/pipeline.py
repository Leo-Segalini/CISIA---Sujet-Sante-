from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src.data.cohort import filter_domicile, patient_level_split
from src.data.features_sortie import build_features_score_sortie
from src.data.features_tele import build_features_score_tele
from src.data.identity import persist_identity_split, split_identity_and_pseudonymise
from src.data.load import copy_sources_to_raw, load_csv
from src.data.paths import CSV_FILES, ProjectPaths
from src.data.quality import (
    filter_objets_connectes_bons,
    harmonize_biologie,
    recalculate_duree_sejour,
)
from src.data.registre import (
    assert_justifications,
    assert_registre_covers_sources,
    build_source_column_index,
    load_registre,
)


def run_pipeline(paths: ProjectPaths, *, horizon_tele: int = 7) -> dict[str, Path]:
    copy_sources_to_raw(paths)
    patients = load_csv(paths, "patients.csv")
    vault, patients_pseudo = split_identity_and_pseudonymise(patients)
    persist_identity_split(paths, vault, patients_pseudo)

    for name in CSV_FILES:
        if name == "patients.csv":
            continue
        shutil.copy2(paths.raw / name, paths.pseudonymise / name)

    registre = load_registre(paths.registres / "registre_colonnes.csv")
    index = build_source_column_index(paths)
    assert_registre_covers_sources(registre, index)
    assert_justifications(registre)

    sejours = recalculate_duree_sejour(load_csv(paths, "sejours.csv"))
    sejours_el = patient_level_split(filter_domicile(sejours))
    historique = load_csv(paths, "historique.csv")
    biologies = harmonize_biologie(load_csv(paths, "biologies.csv"))
    signes = load_csv(paths, "signes_vitaux.csv")
    diagnostics = load_csv(paths, "diagnostics.csv")
    actes = load_csv(paths, "actes.csv")
    medications = load_csv(paths, "medications.csv")
    territoire = load_csv(paths, "territoire_insee.csv")
    objets = filter_objets_connectes_bons(load_csv(paths, "objets_connectes.csv"))

    features_sortie = build_features_score_sortie(
        sejours_el,
        patients_pseudo,
        historique,
        biologies,
        signes,
        diagnostics,
        actes,
        medications,
        territoire,
    )
    features_tele = build_features_score_tele(
        features_sortie, sejours_el, objets, horizon_jours=horizon_tele
    )

    paths.ensure_data_dirs()
    p_el = paths.curated / "sejours_eligibles.parquet"
    p_so = paths.curated / "features_score_sortie.parquet"
    p_te = paths.curated / "features_score_tele.parquet"
    p_rp = paths.curated / "rapport_export.json"
    sejours_el.to_parquet(p_el, index=False)
    features_sortie.to_parquet(p_so, index=False)
    features_tele.to_parquet(p_te, index=False)
    rapport = {
        "n_sejours_eligibles": int(len(sejours_el)),
        "prevalence_readmission": float(sejours_el["Readmission30j"].mean()),
        "n_features_sortie": int(features_sortie.shape[1]),
        "n_features_tele": int(features_tele.shape[1]),
        "colonnes_sortie": list(features_sortie.columns),
        "colonnes_tele": list(features_tele.columns),
        "horizon_tele_jours": horizon_tele,
    }
    p_rp.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sejours_eligibles": p_el,
        "features_score_sortie": p_so,
        "features_score_tele": p_te,
        "rapport": p_rp,
    }
