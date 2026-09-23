"""Ajoute `notebooks/` au PYTHONPATH — importable sans package préalable."""

from __future__ import annotations

import sys
from pathlib import Path

_NB = Path(__file__).resolve().parent
if str(_NB) not in sys.path:
    sys.path.insert(0, str(_NB))
