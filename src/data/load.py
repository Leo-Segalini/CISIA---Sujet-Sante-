from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.data.paths import CSV_FILES, ProjectPaths


def copy_sources_to_raw(paths: ProjectPaths) -> dict[str, Path]:
    paths.ensure_data_dirs()
    out: dict[str, Path] = {}
    missing: list[str] = []
    for name in CSV_FILES:
        src = paths.csv_sources / name
        if not src.exists():
            missing.append(name)
            continue
        dest = paths.raw / name
        shutil.copy2(src, dest)
        out[name] = dest
    if missing:
        raise FileNotFoundError(f"CSV manquants à la racine: {missing}")
    return out


def load_csv(paths: ProjectPaths, name: str, *, from_raw: bool = True) -> pd.DataFrame:
    base = paths.raw if from_raw else paths.csv_sources
    path = base / name
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    return pd.read_csv(path)
