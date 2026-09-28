"""
Registre déclaratif des sources CSV et des étapes pipeline.

Pour étendre sans casser Jupyter / scripts :
1. Ajouter une ``SourceSpec`` dans ``SOURCES`` (nouveau CSV).
2. Ajouter / brancher une ``PipelineStep`` dans ``PIPELINE_STEPS`` (nouvelle étape).
3. Mettre à jour le registre RGPD si la source entre dans le scoring.

Les notebooks consomment ``list_sources()`` / ``describe_pipeline()`` — ils
s’adaptent automatiquement à la liste déclarée ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import pandas as pd

if TYPE_CHECKING:
    from src.data.paths import ProjectPaths


@dataclass(frozen=True)
class SourceSpec:
    """Une source CSV du sujet (ou dérivée)."""

    filename: str
    label: str
    required: bool = True
    role: str = "sujet"  # sujet | derive | optionnel
    description: str = ""


@dataclass(frozen=True)
class PipelineStepSpec:
    """Métadonnée d’une étape (sans la logique)."""

    id: str
    title: str
    description: str
    phase: str = "transform"  # ingest | quality | features | export


# ---------------------------------------------------------------------------
# Sources — point d’extension n°1
# ---------------------------------------------------------------------------

SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec("patients.csv", "Patients", description="Identité et profil patient"),
    SourceSpec("sejours.csv", "Séjours", description="Admissions / sorties / GHM"),
    SourceSpec("historique.csv", "Historique", description="Passé hospitalier 12 mois"),
    SourceSpec("diagnostics.csv", "Diagnostics", description="Codes CIM / diagnostics"),
    SourceSpec("actes.csv", "Actes", description="Actes CCAM / techniques"),
    SourceSpec("biologies.csv", "Biologies", description="Résultats de labo"),
    SourceSpec("signes_vitaux.csv", "Signes vitaux", description="Constantes mesurées"),
    SourceSpec("medications.csv", "Médicaments", description="Prescriptions ATC"),
    SourceSpec("comptes_rendus.csv", "Comptes rendus", description="Texte clinique"),
    SourceSpec(
        "objets_connectes.csv",
        "Objets connectés",
        description="Mesures télé-suivi (poids, etc.)",
    ),
    SourceSpec(
        "territoire_insee.csv",
        "Territoire INSEE",
        description="Proxies territoriaux (sujet)",
    ),
)

# Compat : utilisée partout (load, qualité, registre, notebooks)
CSV_FILES: tuple[str, ...] = tuple(s.filename for s in SOURCES if s.required)


def list_sources(*, required_only: bool = False) -> list[SourceSpec]:
    """Liste des sources déclarées (Jupyter / inventaire)."""
    if required_only:
        return [s for s in SOURCES if s.required]
    return list(SOURCES)


def sources_dataframe() -> pd.DataFrame:
    """Vue tabulaire des sources pour les notebooks."""
    return pd.DataFrame(
        [
            {
                "fichier": s.filename,
                "libelle": s.label,
                "requis": s.required,
                "role": s.role,
                "description": s.description,
            }
            for s in SOURCES
        ]
    )


# ---------------------------------------------------------------------------
# Contexte d’exécution pipeline
# ---------------------------------------------------------------------------


@dataclass
class PipelineContext:
    """État partagé entre étapes — un nouveau bloc lit/écrit ici."""

    paths: ProjectPaths
    horizon_tele: int = 7
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


StepFn = Callable[[PipelineContext], None]


@dataclass(frozen=True)
class PipelineStep:
    """Étape exécutable enregistrée."""

    id: str
    title: str
    description: str
    run: StepFn
    phase: str = "transform"

    def as_spec(self) -> PipelineStepSpec:
        return PipelineStepSpec(
            id=self.id,
            title=self.title,
            description=self.description,
            phase=self.phase,
        )


# Rempli par ``src.data.pipeline_steps.register_default_steps``
_PIPELINE_STEPS: list[PipelineStep] = []


def clear_pipeline_steps() -> None:
    """Réservé aux tests."""
    _PIPELINE_STEPS.clear()


def register_pipeline_step(step: PipelineStep, *, index: int | None = None) -> None:
    """
    Enregistre une étape pipeline.

    - ``index=None`` : append (fin de chaîne)
    - ``index=i`` : insertion (ex. avant l’export)
    """
    ids = {s.id for s in _PIPELINE_STEPS}
    if step.id in ids:
        raise ValueError(f"Étape déjà enregistrée: {step.id}")
    if index is None:
        _PIPELINE_STEPS.append(step)
    else:
        _PIPELINE_STEPS.insert(index, step)


def list_pipeline_steps() -> list[PipelineStep]:
    """Étapes actuelles (après chargement des défauts)."""
    _ensure_defaults_loaded()
    return list(_PIPELINE_STEPS)


def describe_pipeline() -> pd.DataFrame:
    """Résumé lisible pour Jupyter : phases + titres."""
    rows = []
    for i, step in enumerate(list_pipeline_steps(), start=1):
        rows.append(
            {
                "ordre": i,
                "id": step.id,
                "phase": step.phase,
                "titre": step.title,
                "description": step.description,
            }
        )
    return pd.DataFrame(rows)


def _ensure_defaults_loaded() -> None:
    if _PIPELINE_STEPS:
        return
    # Import tardif pour éviter les cycles au chargement du package
    from src.data.pipeline_steps import register_default_steps

    register_default_steps()
