"""Localisation de la racine projet (local + Google Colab)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Dossier contenant patients.csv + Sujet.md."""
    candidates: list[Path] = []

    env = os.environ.get("CISIA_ROOT")
    if env:
        candidates.append(Path(env))

    # Colab / chemins fréquents après unzip de l'archive CIF
    for p in (
        Path("/content/CISIA_Sante"),
        Path("/content/CISIA - Sujet Santé"),
        Path.cwd() / "CISIA_Sante",
    ):
        candidates.append(p)

    cwd = Path.cwd()
    candidates.extend([cwd, *cwd.parents])

    # Notebook téléchargé seul sur Colab : remonter depuis /content
    if Path("/content").is_dir():
        candidates.append(Path("/content"))
        candidates.extend(Path("/content").iterdir())

    seen: set[Path] = set()
    for p in candidates:
        try:
            p = p.resolve()
        except OSError:
            continue
        if p in seen or not p.is_dir():
            continue
        seen.add(p)
        if (p / "patients.csv").is_file() and (p / "Sujet.md").is_file():
            return p

    raise FileNotFoundError(
        "Racine CISIA introuvable (patients.csv + Sujet.md).\n"
        "Sur Colab : uploadez et dézippez l'archive CIF dans /content, puis :\n"
        "  import os; os.chdir('/content/CISIA_Sante')\n"
        "ou définissez : os.environ['CISIA_ROOT'] = '/content/CISIA_Sante'"
    )


def ensure_sys_path(root: Path | None = None) -> Path:
    root = root or find_project_root()
    nb = root / "notebooks"
    for p in (root, nb):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return root
