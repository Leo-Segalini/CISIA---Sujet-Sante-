"""Registry de versions des modèles entraînés."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.data.paths import ProjectPaths


def registry_dir(paths: ProjectPaths) -> Path:
    d = paths.models / "registry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def register_version(
    paths: ProjectPaths,
    *,
    score_name: str,
    metrics: dict[str, Any],
    source: str = "manual",
) -> dict[str, Any]:
    """Archive metrics + bundle sous un identifiant horodaté."""
    reg = registry_dir(paths)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    version_id = f"{score_name}_{ts}"
    dest = reg / version_id
    dest.mkdir(parents=True, exist_ok=True)

    bundle_src = paths.models / f"{score_name}_bundle.joblib"
    metrics_src = paths.models / f"{score_name}_metrics.json"
    if bundle_src.exists():
        shutil.copy2(bundle_src, dest / "bundle.joblib")
    if metrics_src.exists():
        shutil.copy2(metrics_src, dest / "metrics.json")

    meta = {
        "version_id": version_id,
        "score": score_name,
        "retenu": metrics.get("retenu"),
        "ranking": metrics.get("ranking_test_pr_auc"),
        "optuna": metrics.get("optuna", False),
        "source": source,
        "created_at": ts,
    }
    (dest / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    latest = {"latest": version_id, **meta}
    (reg / f"{score_name}_latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def list_versions(paths: ProjectPaths, score_name: str | None = None) -> list[dict]:
    reg = registry_dir(paths)
    out: list[dict] = []
    for p in sorted(reg.glob("*/meta.json")):
        meta = json.loads(p.read_text(encoding="utf-8"))
        if score_name and meta.get("score") != score_name:
            continue
        out.append(meta)
    return out
