"""Surveillance des fichiers modèles pour rechargement à chaud (Docker retrain)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from src.data.paths import ProjectPaths, get_project_root


def _metrics_mtime(paths: ProjectPaths) -> float:
    mtimes = []
    for name in ("score_sortie", "score_tele"):
        p = paths.models / f"{name}_metrics.json"
        if p.exists():
            mtimes.append(p.stat().st_mtime)
    return max(mtimes) if mtimes else 0.0


def start_model_watcher(*, interval_s: float | None = None) -> None:
    """Recharge le store si les métriques modèles changent (conteneur retrain séparé)."""
    if os.environ.get("MODEL_WATCH", "1") == "0":
        return
    interval = interval_s or float(os.environ.get("MODEL_WATCH_INTERVAL", "45"))

    def _loop() -> None:
        paths = ProjectPaths(root=get_project_root())
        last = _metrics_mtime(paths)
        while True:
            time.sleep(interval)
            try:
                current = _metrics_mtime(paths)
                if current > last:
                    from src.web.services import reload_store

                    reload_store()
                    last = current
                    print(f"[model-watch] Modèles rechargés (mtime={current})")
            except Exception as exc:  # noqa: BLE001
                print(f"[model-watch] {exc}")

    threading.Thread(target=_loop, daemon=True, name="model-watch").start()
