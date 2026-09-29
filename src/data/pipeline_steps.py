"""
Étapes pipeline par défaut — branchez un nouveau bloc via ``register_pipeline_step``.

Exemple d’extension (dans un module ou notebook) ::

    from src.data.registry import PipelineStep, register_pipeline_step

    def step_mon_bloc(ctx):
        # lire ctx.frames / écrire ctx.artifacts
        ...

    register_pipeline_step(
        PipelineStep(
            id="mon_bloc",
            title="Mon nouveau bloc",
            description="…",
            run=step_mon_bloc,
            phase="features",
        ),
        index=-1,  # avant export si besoin : calculer l’index via list_pipeline_steps()
    )
"""

from __future__ import annotations

import json
import shutil

from src.data.cohort import filter_domicile, patient_level_split
from src.data.features_sortie import build_features_score_sortie
from src.data.features_tele import build_features_score_tele
from src.data.identity import persist_identity_split, split_identity_and_pseudonymise
from src.data.load import copy_sources_to_raw, load_csv
from src.data.quality import (
    filter_objets_connectes_bons,
    harmonize_biologie,
    recalculate_duree_sejour,
)
from src.data.registre import (
    assert_complements_insee_enregistres,
    assert_justifications,
    assert_registre_covers_sources,
    build_source_column_index,
    load_registre,
)
from src.data.registry import (
    CSV_FILES,
    PipelineContext,
    PipelineStep,
    register_pipeline_step,
)
from src.data.territoire import write_complements


def step_copy_raw(ctx: PipelineContext) -> None:
    """Copie les CSV déclarés (SOURCES dans donnees/) vers data/raw."""
    ctx.artifacts.update(
        {f"raw:{k}": v for k, v in copy_sources_to_raw(ctx.paths).items()}
    )


def step_identity(ctx: PipelineContext) -> None:
    """Coffre identité + patients pseudonymisés."""
    patients = load_csv(ctx.paths, "patients.csv")
    vault, patients_pseudo = split_identity_and_pseudonymise(patients)
    persist_identity_split(ctx.paths, vault, patients_pseudo)
    ctx.frames["patients"] = patients
    ctx.frames["patients_pseudo"] = patients_pseudo
    ctx.frames["vault"] = vault


def step_mirror_pseudonymise(ctx: PipelineContext) -> None:
    """Recopie les autres CSV vers data/pseudonymise (hors patients)."""
    for name in CSV_FILES:
        if name == "patients.csv":
            continue
        shutil.copy2(ctx.paths.raw / name, ctx.paths.pseudonymise / name)


def step_territoire_registre(ctx: PipelineContext) -> None:
    """Territoire sujet + contrôles registre RGPD."""
    territoire_sujet = load_csv(ctx.paths, "territoire_insee.csv")
    write_complements(ctx.paths, territoire_sujet)
    ctx.frames["territoire"] = territoire_sujet
    registre = load_registre(ctx.paths.registres / "registre_colonnes.csv")
    index = build_source_column_index(ctx.paths)
    assert_registre_covers_sources(registre, index)
    assert_justifications(registre)
    assert_complements_insee_enregistres(registre, ctx.paths)
    ctx.frames["registre"] = registre


def step_load_clinical(ctx: PipelineContext) -> None:
    """Charge et harmonise les tables cliniques."""
    sejours = recalculate_duree_sejour(load_csv(ctx.paths, "sejours.csv"))
    sejours_el = patient_level_split(filter_domicile(sejours))
    ctx.frames["sejours"] = sejours
    ctx.frames["sejours_eligibles"] = sejours_el
    ctx.frames["historique"] = load_csv(ctx.paths, "historique.csv")
    ctx.frames["biologies"] = harmonize_biologie(load_csv(ctx.paths, "biologies.csv"))
    ctx.frames["signes"] = load_csv(ctx.paths, "signes_vitaux.csv")
    ctx.frames["diagnostics"] = load_csv(ctx.paths, "diagnostics.csv")
    ctx.frames["actes"] = load_csv(ctx.paths, "actes.csv")
    ctx.frames["medications"] = load_csv(ctx.paths, "medications.csv")
    ctx.frames["objets"] = filter_objets_connectes_bons(
        load_csv(ctx.paths, "objets_connectes.csv")
    )


def step_features(ctx: PipelineContext) -> None:
    """Features score sortie + télé-suivi."""
    f = ctx.frames
    features_sortie = build_features_score_sortie(
        f["sejours_eligibles"],
        f["patients_pseudo"],
        f["historique"],
        f["biologies"],
        f["signes"],
        f["diagnostics"],
        f["actes"],
        f["medications"],
        f["territoire"],
    )
    features_tele = build_features_score_tele(
        features_sortie,
        f["sejours_eligibles"],
        f["objets"],
        horizon_jours=ctx.horizon_tele,
    )
    ctx.frames["features_sortie"] = features_sortie
    ctx.frames["features_tele"] = features_tele


def step_export_curated(ctx: PipelineContext) -> None:
    """Écrit les parquets curated + rapport JSON."""
    ctx.paths.ensure_data_dirs()
    f = ctx.frames
    p_el = ctx.paths.curated / "sejours_eligibles.parquet"
    p_so = ctx.paths.curated / "features_score_sortie.parquet"
    p_te = ctx.paths.curated / "features_score_tele.parquet"
    p_rp = ctx.paths.curated / "rapport_export.json"
    f["sejours_eligibles"].to_parquet(p_el, index=False)
    f["features_sortie"].to_parquet(p_so, index=False)
    f["features_tele"].to_parquet(p_te, index=False)
    from src.data.registry import list_pipeline_steps

    rapport = {
        "n_sejours_eligibles": int(len(f["sejours_eligibles"])),
        "prevalence_readmission": float(f["sejours_eligibles"]["Readmission30j"].mean()),
        "n_features_sortie": int(f["features_sortie"].shape[1]),
        "n_features_tele": int(f["features_tele"].shape[1]),
        "colonnes_sortie": list(f["features_sortie"].columns),
        "colonnes_tele": list(f["features_tele"].columns),
        "horizon_tele_jours": ctx.horizon_tele,
        "etapes": [s.id for s in list_pipeline_steps()],
    }
    p_rp.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    ctx.artifacts.update(
        {
            "sejours_eligibles": p_el,
            "features_score_sortie": p_so,
            "features_score_tele": p_te,
            "rapport": p_rp,
        }
    )
    ctx.meta["rapport"] = rapport


def _default_steps() -> list[PipelineStep]:
    return [
        PipelineStep(
            id="copy_raw",
            title="Copie des sources CSV",
            description="donnees/ → data/raw (copie ; sources intactes)",
            run=step_copy_raw,
            phase="ingest",
        ),
        PipelineStep(
            id="identity",
            title="Pseudonymisation",
            description="Coffre identité + patients sans PII",
            run=step_identity,
            phase="ingest",
        ),
        PipelineStep(
            id="mirror_pseudo",
            title="Miroir pseudonymisé",
            description="Autres CSV vers data/pseudonymise",
            run=step_mirror_pseudonymise,
            phase="ingest",
        ),
        PipelineStep(
            id="territoire_registre",
            title="Territoire & registre RGPD",
            description="INSEE sujet + assertions registre",
            run=step_territoire_registre,
            phase="quality",
        ),
        PipelineStep(
            id="load_clinical",
            title="Tables cliniques",
            description="Séjours éligibles, bio, signes, médics…",
            run=step_load_clinical,
            phase="quality",
        ),
        PipelineStep(
            id="features",
            title="Features ML",
            description="Score sortie 30 j + télé-suivi",
            run=step_features,
            phase="features",
        ),
        PipelineStep(
            id="export_curated",
            title="Export curated",
            description="Parquets + rapport_export.json",
            run=step_export_curated,
            phase="export",
        ),
    ]


def register_default_steps() -> None:
    """Enregistre la chaîne CISIA (idempotent si déjà chargée)."""
    from src.data import registry as reg

    if reg._PIPELINE_STEPS:  # noqa: SLF001
        return
    for step in _default_steps():
        register_pipeline_step(step)
