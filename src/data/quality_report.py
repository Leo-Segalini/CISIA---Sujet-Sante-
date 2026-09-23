"""Rapport qualité des données sources — trous, aberrations, incohérences, sensibilité IA."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

from src.data.load import load_csv
from src.data.paths import CSV_FILES, ProjectPaths
from src.data.quality import (
    harmonize_biologie,
    recalculate_duree_sejour,
)
from src.data.registre import load_registre
from src.data.vitals import enrich_signes_vitaux

SENSIBILITE_ORDER = (
    "identite_directe",
    "sante_art9",
    "proxy_socio",
    "faible",
    "aucune",
)
USAGE_IA_ORDER = ("autorise", "flag_only", "exclu")


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _bar_chart(
    labels: list[str],
    values: list[float],
    *,
    title: str,
    xlabel: str,
    color: str = "#003735",
) -> str | None:
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(labels))))
    y_pos = range(len(labels))
    ax.barh(list(y_pos), values, color=color, alpha=0.85)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=11)
    ax.set_xlim(0, min(1.05, max(values) * 1.15 + 0.02) if values else 1)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _stacked_usage_chart(rows: list[dict[str, Any]], *, title: str) -> str | None:
    if not rows:
        return None
    usages = list(USAGE_IA_ORDER)
    colors = {"autorise": "#2d6765", "flag_only": "#ba8c2e", "exclu": "#ba1a1a"}
    labels = [r["colonne"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(labels))))
    left = [0.0] * len(labels)
    y_pos = range(len(labels))
    for usage in usages:
        widths = [1.0 if r["usage_score_sortie"] == usage else 0.0 for r in rows]
        ax.barh(list(y_pos), widths, left=left, label=f"sortie · {usage}", color=colors[usage], alpha=0.9)
        left = [l + w for l, w in zip(left, widths)]
    left = [0.0] * len(labels)
    for usage in usages:
        widths = [1.0 if r["usage_score_tele"] == usage else 0.0 for r in rows]
        ax.barh(
            [y + 0.35 for y in y_pos],
            widths,
            left=left,
            height=0.3,
            label=f"télé · {usage}" if usage == usages[0] else f"_télé · {usage}",
            color=colors[usage],
            alpha=0.55,
        )
        left = [l + w for l, w in zip(left, widths)]
    ax.set_yticks([y + 0.15 for y in y_pos])
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Usage IA (1 = colonne entière)")
    ax.set_title(title, fontsize=11)
    handles, lbls = ax.get_legend_handles_labels()
    uniq: dict[str, Any] = {}
    for h, l in zip(handles, lbls):
        if not l.startswith("_"):
            uniq[l] = h
    ax.legend(uniq.values(), uniq.keys(), loc="lower right", fontsize=8)
    fig.tight_layout()
    return _fig_to_base64(fig)


def missing_rates(df: pd.DataFrame) -> dict[str, float]:
    n = max(len(df), 1)
    out: dict[str, float] = {}
    for col in df.columns:
        s = df[col]
        if s.dtype == object:
            empty = s.isna() | s.astype(str).str.strip().eq("")
        else:
            empty = s.isna()
        out[col] = float(empty.sum()) / n
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def _dates_hors_sejour(
    events: pd.DataFrame,
    sejours: pd.DataFrame,
    *,
    date_col: str,
    sejour_col: str = "SejourID",
) -> pd.Series:
    if sejour_col not in events.columns:
        return pd.Series(False, index=events.index)
    ref = sejours.set_index(sejour_col)[["DateAdmission", "DateSortie"]]
    merged = events.merge(ref, left_on=sejour_col, right_index=True, how="left")
    dates = pd.to_datetime(merged[date_col], errors="coerce")
    adm = pd.to_datetime(merged["DateAdmission"], errors="coerce")
    sortie = pd.to_datetime(merged["DateSortie"], errors="coerce")
    return dates.isna() | dates.lt(adm) | dates.gt(sortie)


def aberrant_rates(name: str, df: pd.DataFrame) -> dict[str, float]:
    """Valeurs impossibles (hors plage physiologique ou biologique élargie)."""
    n = max(len(df), 1)
    out: dict[str, float] = {}
    if name == "signes_vitaux.csv":
        flagged = enrich_signes_vitaux(df)
        for col in flagged.columns:
            if col.startswith("flag_") and col != "flag_tension_incoherente":
                out[col.replace("flag_", "").replace("_aberrant", "")] = float(
                    flagged[col].mean()
                )
    elif name == "biologies.csv":
        bio = harmonize_biologie(df)
        out["biologie_hors_ref"] = float(bio["flag_biologie_aberrante"].mean())
    return out


def mal_note_rates(
    name: str, df: pd.DataFrame, *, sejours: pd.DataFrame | None = None
) -> dict[str, float]:
    """Valeurs contradictoires ou mal saisies (incohérence métier)."""
    n = max(len(df), 1)
    out: dict[str, float] = {}
    if name == "sejours.csv":
        sj = recalculate_duree_sejour(df)
        out["duree_incoherente"] = float(sj["flag_duree_incoherente"].mean())
    elif name == "signes_vitaux.csv":
        flagged = enrich_signes_vitaux(df)
        out["tension_diastole_ge_systole"] = float(
            flagged["flag_tension_incoherente"].mean()
        )
    elif name == "objets_connectes.csv" and "QualiteSignal" in df.columns:
        out["signal_non_bon"] = float((df["QualiteSignal"] != "Bon").mean())
    elif sejours is not None:
        sejour_col_date = _event_date_col(name, df)
        if sejour_col_date:
            hors = _dates_hors_sejour(df, sejours, date_col=sejour_col_date)
            out[f"{sejour_col_date}_hors_sejour"] = float(hors.mean())
    return out


def _event_date_col(name: str, df: pd.DataFrame) -> str | None:
    mapping = {
        "actes.csv": "DateActe",
        "medications.csv": "DateDebut",
        "comptes_rendus.csv": "DateCR",
    }
    col = mapping.get(name)
    if col and col in df.columns and "SejourID" in df.columns:
        return col
    return None


def sensibilite_ia_table(registre: pd.DataFrame, fichier: str) -> list[dict[str, str]]:
    sub = registre.loc[registre["fichier_source"] == fichier].copy()
    if sub.empty:
        return []
    sub = sub.sort_values(["sensibilite", "colonne"])
    return sub[
        ["colonne", "sensibilite", "usage_score_sortie", "usage_score_tele", "risque_principal"]
    ].to_dict(orient="records")


def sensibilite_counts(registre: pd.DataFrame, fichier: str) -> dict[str, int]:
    sub = registre.loc[registre["fichier_source"] == fichier]
    return {k: int(v) for k, v in sub["sensibilite"].value_counts().items()}


def analyze_dataset(
    name: str,
    df: pd.DataFrame,
    registre: pd.DataFrame,
    *,
    sejours: pd.DataFrame | None = None,
) -> dict[str, Any]:
    trous = missing_rates(df)
    aberrants = aberrant_rates(name, df)
    mal_notes = mal_note_rates(name, df, sejours=sejours)
    sensibilite = sensibilite_ia_table(registre, name)
    return {
        "fichier": name,
        "n_lignes": int(len(df)),
        "n_colonnes": int(len(df.columns)),
        "trous": trous,
        "aberrants": aberrants,
        "mal_notes": mal_notes,
        "sensibilite_ia": sensibilite,
        "sensibilite_counts": sensibilite_counts(registre, name),
    }


def _charts_for_dataset(report: dict[str, Any]) -> dict[str, str | None]:
    fichier = report["fichier"]
    charts: dict[str, str | None] = {}

    trous = report["trous"]
    if trous:
        top = list(trous.items())[:20]
        charts["trous"] = _bar_chart(
            [k for k, _ in top],
            [v for _, v in top],
            title=f"{fichier} — taux de valeurs manquantes",
            xlabel="Part des lignes (0–1)",
            color="#515f74",
        )

    aberrants = report["aberrants"]
    if aberrants:
        charts["aberrants"] = _bar_chart(
            list(aberrants.keys()),
            list(aberrants.values()),
            title=f"{fichier} — valeurs aberrantes (hors plage)",
            xlabel="Part des lignes (0–1)",
            color="#ba1a1a",
        )

    mal_notes = report["mal_notes"]
    if mal_notes:
        charts["mal_notes"] = _bar_chart(
            list(mal_notes.keys()),
            list(mal_notes.values()),
            title=f"{fichier} — valeurs mal notées / incohérentes",
            xlabel="Part des lignes (0–1)",
            color="#ba8c2e",
        )

    sens = report["sensibilite_ia"]
    if sens:
        charts["sensibilite_ia"] = _stacked_usage_chart(
            sens,
            title=f"{fichier} — sensibilité & usage IA (sortie / télé)",
        )
    return charts


def run_quality_report(paths: ProjectPaths) -> dict[str, Any]:
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    sejours_raw = load_csv(paths, "sejours.csv", from_raw=False)
    sejours = recalculate_duree_sejour(sejours_raw)

    datasets: list[dict[str, Any]] = []
    for name in CSV_FILES:
        df = load_csv(paths, name, from_raw=False)
        rep = analyze_dataset(name, df, registre, sejours=sejours)
        rep["charts"] = _charts_for_dataset(rep)
        datasets.append(rep)

    full = {
        "n_fichiers": len(datasets),
        "datasets": datasets,
        "note": (
            "Trous = NA ou chaîne vide. Aberrant = hors plage physiologique/biologique. "
            "Mal noté = incohérence métier (durée, tension, date hors séjour, signal OC). "
            "Sensibilité IA = registre registre_colonnes.csv (usage score sortie / télé)."
        ),
    }
    return full


def write_quality_html(report: dict[str, Any], html_path: Path) -> Path:
    sections: list[str] = []
    for ds in report["datasets"]:
        charts = ds.get("charts") or {}
        imgs = []
        for key, label in (
            ("trous", "Valeurs manquantes"),
            ("aberrants", "Valeurs aberrantes"),
            ("mal_notes", "Valeurs mal notées"),
            ("sensibilite_ia", "Sensibilité & usage IA"),
        ):
            b64 = charts.get(key)
            if b64:
                imgs.append(
                    f'<figure><figcaption>{label}</figcaption>'
                    f'<img alt="{label} — {ds["fichier"]}" src="data:image/png;base64,{b64}"/></figure>'
                )
        sens_rows = "".join(
            f"<tr><td>{r['colonne']}</td><td>{r['sensibilite']}</td>"
            f"<td>{r['usage_score_sortie']}</td><td>{r['usage_score_tele']}</td>"
            f"<td>{r.get('risque_principal','')}</td></tr>"
            for r in ds.get("sensibilite_ia", [])
        )
        sections.append(
            f"""
<section class="dataset">
  <h2>{ds['fichier']}</h2>
  <p class="meta">{ds['n_lignes']:,} lignes · {ds['n_colonnes']} colonnes</p>
  <div class="charts">{''.join(imgs) or '<p class="muted">Aucun graphique pour ce fichier.</p>'}</div>
  <details>
    <summary>Tableau sensibilité IA (registre)</summary>
    <table>
      <thead><tr><th>Colonne</th><th>Sensibilité</th><th>Score sortie</th><th>Score télé</th><th>Risque</th></tr></thead>
      <tbody>{sens_rows or '<tr><td colspan="5">—</td></tr>'}</tbody>
    </table>
  </details>
</section>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <title>Rapport qualité données — CISIA Santé</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1100px; color: #1a1a1a; }}
    h1 {{ color: #003735; }}
    h2 {{ margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }}
    .meta {{ color: #515f74; }}
    .charts {{ display: grid; gap: 1.5rem; }}
    figure {{ margin: 0; }}
    figcaption {{ font-weight: 600; margin-bottom: 0.5rem; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; margin-top: 0.5rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #f4f6f6; }}
    .muted {{ color: #666; }}
    .note {{ background: #f4f6f6; padding: 1rem; border-radius: 6px; margin: 1rem 0; }}
  </style>
</head>
<body>
  <h1>Rapport qualité des données sources</h1>
  <p class="note">{report['note']}</p>
  <p><strong>{report['n_fichiers']}</strong> jeux de données analysés.</p>
  {''.join(sections)}
</body>
</html>"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return html_path


def export_quality_report(paths: ProjectPaths) -> dict[str, Path]:
    report = run_quality_report(paths)
    out_dir = paths.curated / "qualite"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rapport_qualite.json"
    html_path = out_dir / "rapport_qualite.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_quality_html(report, html_path)
    return {"json": json_path, "html": html_path}
