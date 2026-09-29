from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.data.paths import ProjectPaths
from src.data.registry import CSV_FILES

# Préserve les zéros non significatifs (ex. CodePostal 03200) sans toucher aux CSV sources.
_DTYPE_BY_FILE: dict[str, dict[str, type]] = {
    "patients.csv": {"CodePostal": str},
}


def copy_sources_to_raw(paths: ProjectPaths) -> dict[str, Path]:
    """Duplique `donnees/*.csv` → `data/raw/` (sources jamais modifiées)."""
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
        raise FileNotFoundError(
            f"CSV manquants dans {paths.csv_sources}/ : {missing}"
        )
    return out


def load_csv(paths: ProjectPaths, name: str, *, from_raw: bool = True) -> pd.DataFrame:
    """Charge un CSV depuis data/raw (défaut) ou depuis donnees/ (from_raw=False)."""
    base = paths.raw if from_raw else paths.csv_sources
    path = base / name
    if not path.exists():
        # Repli : si raw absent, copie depuis donnees puis recharge
        if from_raw and (paths.csv_sources / name).exists():
            paths.ensure_data_dirs()
            shutil.copy2(paths.csv_sources / name, path)
        else:
            raise FileNotFoundError(f"Fichier introuvable: {path}")
    dtype = _DTYPE_BY_FILE.get(name)
    return pd.read_csv(path, dtype=dtype)
