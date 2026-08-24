from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.data.pipeline import run_pipeline


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    out = run_pipeline(paths, horizon_tele=7)
    for k, p in out.items():
        print(f"{k}: {p}")


if __name__ == "__main__":
    main()
