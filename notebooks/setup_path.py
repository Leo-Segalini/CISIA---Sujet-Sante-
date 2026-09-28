"""Ajoute la racine projet + ``notebooks/`` au PYTHONPATH.

Les notebooks restent agnostiques : ``describe_pipeline()`` / ``sources_dataframe()``
suivent le registre ``src.data.registry`` sans modification des cellules.
"""

from __future__ import annotations

import sys
from pathlib import Path

_NB = Path(__file__).resolve().parent
_ROOT = _NB.parent

for _p in (_ROOT, _NB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
