"""Configuration commune des notebooks CISIA."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent
ROOT = NOTEBOOKS_DIR.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(NOTEBOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS_DIR))

from src.data.paths import ProjectPaths, get_project_root  # noqa: E402

paths = ProjectPaths(root=get_project_root())

plt.style.use("seaborn-v0_8-whitegrid")
pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 120)

COLORS = {
    "trous": "#515f74",
    "aberrant": "#ba1a1a",
    "mal_note": "#ba8c2e",
    "sensibilite": "#2d6765",
}
