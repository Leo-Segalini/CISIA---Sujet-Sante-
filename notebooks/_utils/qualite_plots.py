"""Graphiques qualité pour notebooks Jupyter (affichage inline)."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from _utils.bootstrap import COLORS


def _barh(ax, labels: list[str], values: list[float], *, title: str, xlabel: str, color: str):
    if not labels:
        ax.text(0.5, 0.5, "Aucune anomalie détectée", ha="center", va="center")
        ax.set_axis_off()
        return
    y = range(len(labels))
    ax.barh(list(y), values, color=color, alpha=0.88)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlim(0, min(1.05, max(values) * 1.2 + 0.02))
    ax.grid(axis="x", alpha=0.3)


def plot_dataset_qualite(ds: dict[str, Any], *, fichier: str | None = None) -> None:
    """4 graphiques : trous, aberrants, mal notés, synthèse."""
    nom = fichier or ds["fichier"]
    fig, axes = plt.subplots(2, 2, figsize=(14, max(5, 0.25 * len(ds.get("trous", {})))))
    fig.suptitle(f"Qualité — {nom}", fontsize=13, fontweight="bold")

    trous = ds.get("trous", {})
    top_trous = sorted(trous.items(), key=lambda x: x[1], reverse=True)[:15]
    _barh(
        axes[0, 0],
        [k for k, _ in top_trous],
        [v for _, v in top_trous],
        title="Trous (valeurs manquantes)",
        xlabel="Part des lignes",
        color=COLORS["trous"],
    )

    ab = ds.get("aberrants", {})
    _barh(
        axes[0, 1],
        list(ab.keys()),
        list(ab.values()),
        title="Valeurs aberrantes (hors plage)",
        xlabel="Part des lignes",
        color=COLORS["aberrant"],
    )

    mn = ds.get("mal_notes", {})
    _barh(
        axes[1, 0],
        list(mn.keys()),
        list(mn.values()),
        title="Valeurs mal notées / incohérentes",
        xlabel="Part des lignes",
        color=COLORS["mal_note"],
    )

    # Synthèse chiffres
    ax = axes[1, 1]
    ax.axis("off")
    lines = [
        f"Lignes : {ds['n_lignes']:,}",
        f"Colonnes : {ds['n_colonnes']}",
        f"Colonnes IA (registre) : {len(ds.get('sensibilite_ia', []))}",
        "",
        "Taux max. manquant : "
        f"{max(trous.values()) * 100:.1f} %" if trous else "—",
        "Types aberrants : " + str(len(ab)),
        "Types incohérents : " + str(len(mn)),
    ]
    ax.text(0.05, 0.95, "\n".join(lines), va="top", fontsize=11, family="monospace")

    plt.tight_layout()
    plt.show()


def plot_sensibilite_ia(rows: list[dict[str, str]], *, fichier: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(10, max(3, 0.35 * len(df))))
    colors = {"autorise": "#2d6765", "flag_only": "#ba8c2e", "exclu": "#ba1a1a"}
    y = range(len(df))
    for usage, color in colors.items():
        mask = df["usage_score_sortie"] == usage
        ax.barh(
            [i for i, m in zip(y, mask) if m],
            [1] * mask.sum(),
            color=color,
            alpha=0.85,
            label=f"sortie · {usage}",
        )
    ax.set_yticks(list(y))
    ax.set_yticklabels(df["colonne"], fontsize=9)
    ax.set_xlim(0, 1.05)
    ax.set_title(f"Sensibilité & usage IA — {fichier}", fontweight="bold")
    ax.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    plt.show()


def plot_synthese_globale(report: dict[str, Any]) -> None:
    rows = []
    for ds in report["datasets"]:
        rows.append(
            {
                "fichier": ds["fichier"].replace(".csv", ""),
                "trous_max": max(ds["trous"].values()) if ds["trous"] else 0,
                "aberrants": sum(ds["aberrants"].values()) if ds["aberrants"] else 0,
                "mal_notes": sum(ds["mal_notes"].values()) if ds["mal_notes"] else 0,
            }
        )
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(df))
    w = 0.25
    ax.bar([i - w for i in x], df["trous_max"], width=w, label="Trous (max)", color=COLORS["trous"])
    ax.bar(x, df["aberrants"], width=w, label="Aberrants (Σ)", color=COLORS["aberrant"])
    ax.bar([i + w for i in x], df["mal_notes"], width=w, label="Mal notés (Σ)", color=COLORS["mal_note"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["fichier"], rotation=35, ha="right")
    ax.set_ylabel("Taux / somme des taux")
    ax.set_title("Synthèse qualité — tous les fichiers sources", fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.show()
