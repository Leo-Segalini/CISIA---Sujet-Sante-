"""Graphiques qualité pour notebooks Jupyter (affichage inline)."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from _utils.bootstrap import COLORS

# Évite le spam « More than 20 figures have been opened »
plt.rcParams["figure.max_open_warning"] = 50


def _afficher(fig: plt.Figure) -> None:
    """Affiche une figure dans Jupyter puis la ferme (évite Agg + fuites mémoire)."""
    try:
        from IPython.display import display

        display(fig)
    except Exception:
        pass
    finally:
        plt.close(fig)


def _barh(ax, labels: list[str], values: list[float], *, title: str, xlabel: str, color: str):
    # Ne garder que les taux > 0 (sinon barres invisibles → impression « pas de graphique »)
    pairs = [(lab, val) for lab, val in zip(labels, values) if val is not None and float(val) > 0]
    if not pairs:
        ax.text(
            0.5,
            0.5,
            "Aucune anomalie détectée\n(taux = 0 %)",
            ha="center",
            va="center",
            fontsize=11,
            color="#515f74",
        )
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        return
    labels_f, values_f = zip(*pairs)
    y = range(len(labels_f))
    ax.barh(list(y), list(values_f), color=color, alpha=0.88)
    ax.set_yticks(list(y))
    ax.set_yticklabels(list(labels_f), fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlim(0, min(1.05, max(values_f) * 1.2 + 0.02))
    ax.grid(axis="x", alpha=0.3)


def plot_dataset_qualite(ds: dict[str, Any], *, fichier: str | None = None) -> None:
    """4 graphiques : trous, aberrants, mal notés, synthèse."""
    nom = fichier or ds["fichier"]
    trous = ds.get("trous", {})
    # Uniquement colonnes avec manquants > 0, top 15
    top_trous = sorted(
        ((k, v) for k, v in trous.items() if v and float(v) > 0),
        key=lambda x: x[1],
        reverse=True,
    )[:15]
    ab = {k: v for k, v in ds.get("aberrants", {}).items() if v and float(v) > 0}
    mn = {k: v for k, v in ds.get("mal_notes", {}).items() if v and float(v) > 0}

    fig, axes = plt.subplots(2, 2, figsize=(14, max(5.5, 0.35 * max(len(top_trous), 4))))
    fig.suptitle(f"Qualité — {nom}", fontsize=13, fontweight="bold")

    _barh(
        axes[0, 0],
        [k for k, _ in top_trous],
        [v for _, v in top_trous],
        title="Trous (valeurs manquantes)",
        xlabel="Part des lignes",
        color=COLORS["trous"],
    )

    _barh(
        axes[0, 1],
        list(ab.keys()),
        list(ab.values()),
        title="Valeurs aberrantes (hors plage)",
        xlabel="Part des lignes",
        color=COLORS["aberrant"],
    )

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
    trous_max = max((float(v) for v in trous.values() if v), default=0.0)
    lines = [
        f"Lignes : {ds['n_lignes']:,}",
        f"Colonnes : {ds['n_colonnes']}",
        f"Colonnes IA (registre) : {len(ds.get('sensibilite_ia', []))}",
        "",
        f"Taux max. manquant : {trous_max * 100:.1f} %",
        f"Colonnes avec trous : {len(top_trous)}",
        f"Types aberrants : {len(ab)}",
        f"Types incohérents : {len(mn)}",
    ]
    ax.text(0.05, 0.95, "\n".join(lines), va="top", fontsize=11, family="monospace")

    fig.tight_layout()
    _afficher(fig)


def plot_sensibilite_ia(rows: list[dict[str, str]], *, fichier: str) -> None:
    """Répartition quantitative (comptages) + tableau colonne → usage IA."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    usage_order = ["autorise", "flag_only", "exclu"]
    usage_colors = {"autorise": "#2d6765", "flag_only": "#ba8c2e", "exclu": "#ba1a1a"}
    sens_order = ["identite_directe", "sante_art9", "proxy_socio", "faible", "aucune"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    fig.suptitle(f"Sensibilité & usage IA — {fichier}", fontsize=13, fontweight="bold")

    # Panneau gauche : nb de colonnes par usage (sortie + télé)
    ax = axes[0]
    c_sortie = df["usage_score_sortie"].value_counts().reindex(usage_order, fill_value=0)
    c_tele = df["usage_score_tele"].value_counts().reindex(usage_order, fill_value=0)
    y = range(len(usage_order))
    h = 0.35
    ax.barh(
        [i - h / 2 for i in y],
        c_sortie.values,
        height=h,
        color=[usage_colors[u] for u in usage_order],
        alpha=0.95,
        label="Score sortie",
    )
    ax.barh(
        [i + h / 2 for i in y],
        c_tele.values,
        height=h,
        color=[usage_colors[u] for u in usage_order],
        alpha=0.45,
        label="Score télé",
    )
    ax.set_yticks(list(y))
    ax.set_yticklabels(usage_order)
    ax.set_xlabel("Nombre de colonnes")
    ax.set_title("Usage modèle (comptages)", fontsize=11)
    xmax = max(int(c_sortie.max()), int(c_tele.max()), 1)
    ax.set_xlim(0, xmax + 1)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)

    # Panneau droit : nb de colonnes par niveau de sensibilité RGPD
    ax = axes[1]
    present = [s for s in sens_order if s in set(df["sensibilite"])]
    extra = [s for s in df["sensibilite"].unique() if s not in sens_order]
    labels_s = present + extra
    counts_s = df["sensibilite"].value_counts().reindex(labels_s, fill_value=0)
    ax.barh(list(range(len(labels_s))), counts_s.values, color=COLORS["sensibilite"], alpha=0.88)
    ax.set_yticks(list(range(len(labels_s))))
    ax.set_yticklabels(labels_s)
    ax.set_xlabel("Nombre de colonnes")
    ax.set_title("Sensibilité RGPD (comptages)", fontsize=11)
    ax.set_xlim(0, max(int(counts_s.max()), 1) + 1)
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    _afficher(fig)

    # Détail lisible : une ligne = une colonne (pas une barre factice à 1.0)
    try:
        from IPython.display import Markdown, display

        detail = df[
            ["colonne", "sensibilite", "usage_score_sortie", "usage_score_tele", "risque_principal"]
        ].sort_values(["usage_score_sortie", "sensibilite", "colonne"])
        display(Markdown(f"**Détail colonnes — `{fichier}`**"))
        display(detail.reset_index(drop=True))
    except Exception:
        pass


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
    fig.tight_layout()
    _afficher(fig)
