#!/usr/bin/env python3
"""Génère le rapport qualité HTML + JSON (trous, aberrations, incohérences, sensibilité IA)."""

from __future__ import annotations

from src.data.paths import ProjectPaths, get_project_root
from src.data.quality_report import export_quality_report


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    out = export_quality_report(paths)
    print("Rapport qualité généré :")
    for k, p in out.items():
        print(f"  {k}: {p}")


if __name__ == "__main__":
    main()
