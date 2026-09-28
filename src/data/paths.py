from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IDENTITY_COLUMNS = ("NomPrenom", "PersonneAPrevenir")


def __getattr__(name: str):
    """Compat : ``CSV_FILES`` vit dans le registre déclaratif."""
    if name == "CSV_FILES":
        from src.data.registry import CSV_FILES

        return CSV_FILES
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def vault(self) -> Path:
        return self.root / "data" / "vault_identite"

    @property
    def pseudonymise(self) -> Path:
        return self.root / "data" / "pseudonymise"

    @property
    def curated(self) -> Path:
        return self.root / "data" / "curated"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def registres(self) -> Path:
        return self.root / "docs" / "registres"

    @property
    def csv_sources(self) -> Path:
        """CSV pédagogiques fournis à la racine du sujet."""
        return self.root

    def ensure_data_dirs(self) -> None:
        for p in (
            self.raw,
            self.vault,
            self.pseudonymise,
            self.curated,
            self.registres,
            self.models,
        ):
            p.mkdir(parents=True, exist_ok=True)


def get_project_root() -> Path:
    """Remonte jusqu'au dossier contenant Sujet.md et patients.csv."""
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "Sujet.md").exists() and (candidate / "patients.csv").exists():
            return candidate
    raise FileNotFoundError("Racine projet introuvable (Sujet.md + patients.csv).")
