#!/usr/bin/env python3
"""Régénère documentation/assets/comparaison_modeles_rf.png depuis score_sortie_metrics.json.

Palette d’origine (#5b8def / #3dcfb0), fond transparent.
Annotations : RETENU prod + éventuellement 1ᵉʳ PR-AUC / meilleur F2.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "models" / "score_sortie_metrics.json"
OUT = ROOT / "documentation" / "assets" / "comparaison_modeles_rf.png"
PROD_SCORE_SORTIE = "random_forest"

ORDER = [
    "reference",
    "mlp",
    "hist_gradient_boosting",
    "logistic",
    "lightgbm",
    "random_forest",
]

# Palette d’origine (barres) + noir pour texte / flèches / légende (fond transparent)
COLOR_PR = "#5b8def"
COLOR_F2 = "#3dcfb0"
COLOR_INK = "#000000"
COLOR_GRID = "#5a6a7e"
COLOR_SPINE = "#3a4a5e"


def main() -> None:
    data = json.loads(METRICS.read_text(encoding="utf-8"))
    retenu = PROD_SCORE_SORTIE
    ranking = list(data.get("ranking_test_pr_auc") or [])
    meilleur = data.get("meilleur_benchmark") or (ranking[0] if ranking else None)

    keys_plot: list[str] = []
    labels: list[str] = []
    pr: list[float] = []
    f2: list[float] = []
    for key in ORDER:
        block = data.get(key)
        if not block or "test" not in block:
            continue
        keys_plot.append(key)
        labels.append(block.get("label", key))
        pr.append(float(block["test"]["pr_auc"]))
        f2.append(float(block["test"]["f2"]))

    if not keys_plot:
        raise SystemExit("Aucun modèle plottable dans score_sortie_metrics.json")

    if meilleur not in keys_plot:
        meilleur = keys_plot[int(np.argmax(pr))]
    if retenu not in keys_plot:
        retenu = meilleur

    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(12.0, 5.6), dpi=160)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    bars_pr = ax.bar(
        x - width / 2,
        pr,
        width,
        label="PR-AUC test (critère de choix)",
        color=COLOR_PR,
        zorder=3,
    )
    bars_f2 = ax.bar(
        x + width / 2,
        f2,
        width,
        label="F2 test (seuil calé sur validation)",
        color=COLOR_F2,
        zorder=3,
    )

    for bars in (bars_pr, bars_f2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.02,
                f"{h:.2f}",
                ha="center",
                va="bottom",
                color=COLOR_INK,
                fontsize=9,
                fontweight="bold",
            )

    ax.set_ylabel("Score (0–1)", color=COLOR_INK, fontsize=11)
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=COLOR_INK, fontsize=8.5, rotation=15, ha="right")
    ax.tick_params(axis="y", colors=COLOR_INK)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35, color=COLOR_GRID)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(COLOR_SPINE)

    leg = ax.legend(
        loc="upper left",
        frameon=True,
        facecolor="white",
        edgecolor=COLOR_INK,
        labelcolor=COLOR_INK,
        fontsize=9,
    )
    leg.get_frame().set_alpha(0.92)

    idx_retenu = keys_plot.index(retenu)
    idx_best = keys_plot.index(meilleur)
    bar_retenu = bars_pr[idx_retenu]
    same = retenu == meilleur
    label_retenu = (
        "RETENU\nmeilleur PR-AUC" if same else "RETENU prod\n(RF figé)"
    )
    ax.annotate(
        label_retenu,
        xy=(bar_retenu.get_x() + bar_retenu.get_width() / 2, bar_retenu.get_height()),
        xytext=(
            bar_retenu.get_x() + bar_retenu.get_width() / 2 + 0.85,
            min(0.95, bar_retenu.get_height() + 0.22),
        ),
        color=COLOR_INK,
        fontsize=9,
        fontweight="bold",
        ha="center",
        va="center",
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "#ffffff",
            "edgecolor": COLOR_INK,
            "linewidth": 1.5,
        },
        arrowprops={
            "arrowstyle": "->",
            "color": COLOR_INK,
            "lw": 1.4,
            "connectionstyle": "arc3,rad=0.12",
        },
    )

    if not same:
        bar_best = bars_pr[idx_best]
        ax.annotate(
            "1ᵉʳ PR-AUC\n(benchmark)",
            xy=(bar_best.get_x() + bar_best.get_width() / 2, bar_best.get_height()),
            xytext=(
                bar_best.get_x() + bar_best.get_width() / 2 - 0.85,
                min(0.95, bar_best.get_height() + 0.22),
            ),
            color=COLOR_INK,
            fontsize=9,
            fontweight="bold",
            ha="center",
            va="center",
            bbox={
                "boxstyle": "round,pad=0.45",
                "facecolor": "#ffffff",
                "edgecolor": COLOR_INK,
                "linewidth": 1.5,
            },
            arrowprops={
                "arrowstyle": "->",
                "color": COLOR_INK,
                "lw": 1.4,
                "connectionstyle": "arc3,rad=-0.12",
            },
        )

    if "lightgbm" in keys_plot:
        idx_lgb = keys_plot.index("lightgbm")
        if f2[idx_lgb] >= max(f2) - 1e-9 and idx_lgb != idx_retenu:
            bar_f = bars_f2[idx_lgb]
            ax.annotate(
                "meilleur F2\n≠ critère prod",
                xy=(bar_f.get_x() + bar_f.get_width() / 2, bar_f.get_height()),
                xytext=(
                    bar_f.get_x() + bar_f.get_width() / 2 - 0.9,
                    min(1.0, bar_f.get_height() + 0.18),
                ),
                color=COLOR_INK,
                fontsize=8.5,
                fontweight="bold",
                ha="center",
                va="center",
                bbox={
                    "boxstyle": "round,pad=0.4",
                    "facecolor": "#ffffff",
                    "edgecolor": COLOR_INK,
                    "linewidth": 1.4,
                },
                arrowprops={
                    "arrowstyle": "->",
                    "color": COLOR_INK,
                    "lw": 1.3,
                    "connectionstyle": "arc3,rad=-0.12",
                },
            )

    delta = pr[idx_best] - pr[idx_retenu]
    ax.set_title(
        f"Score sortie — comparaison modèles (retenu : {data.get(retenu, {}).get('label', retenu)})",
        color=COLOR_INK,
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        OUT,
        facecolor="none",
        edgecolor="none",
        transparent=True,
        bbox_inches="tight",
    )
    plt.close(fig)
    print(
        f"écrit {OUT} (retenu_prod={retenu}, meilleur_pr_auc={meilleur}, "
        f"ecart={delta:+.4f}, fond=transparent)"
    )


if __name__ == "__main__":
    main()
