#!/usr/bin/env python3
"""Promotion production hôpital : RF sortie + logistic télé, calibrés, registry, monitoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.mlops.production import PRODUCTION_MODELS, promote_all_to_production


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    print("Modèles prod figés :", PRODUCTION_MODELS)
    result = promote_all_to_production(paths, source="promote_production")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"\n✓ Manifeste : {result['manifest']}")
    print("✓ Bundles calibrés + registry + baselines monitoring prêts pour l'hôpital.")


if __name__ == "__main__":
    main()
