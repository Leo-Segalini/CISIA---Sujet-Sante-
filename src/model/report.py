"""Rapport HTML/JSON du benchmark modèles (courbes ROC / PR)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _plot_curves(
    curves: dict[str, dict],
    *,
    kind: str,
    split: str,
) -> str:
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = ["#003735", "#515f74", "#693b24", "#2d6765", "#ba1a1a", "#6b4c9a"]
    for i, (name, data) in enumerate(curves.items()):
        key = f"{kind}_{split}"
        pts = data.get(key, [])
        if not pts:
            continue
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        ax.plot(xs, ys, label=name, color=colors[i % len(colors)], linewidth=2)
    ax.set_xlabel("Rappel" if kind == "pr" else "Faux positifs (1 − spécificité)")
    ax.set_ylabel("Précision" if kind == "pr" else "Vrai positifs (sensibilité)")
    title = "Courbe PR" if kind == "pr" else "Courbe ROC"
    ax.set_title(f"{title} — jeu {split}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    return _fig_to_base64(fig)


def _metrics_table(report: dict) -> str:
    rows = []
    for key in report.get("ranking_test_pr_auc", []):
        m = report["modeles"][key]
        test = m["test"]
        rows.append(
            f"<tr><td>{m['label']}</td>"
            f"<td class='num'>{test['pr_auc']:.3f}</td>"
            f"<td class='num'>{test['roc_auc']:.3f}</td>"
            f"<td class='num'>{test['f2']:.3f}</td>"
            f"<td class='num'>{test['recall']:.3f}</td>"
            f"<td class='num'>{test['precision']:.3f}</td>"
            f"<td class='num'>{test['threshold']:.2f}</td>"
            f"{'<td>★</td>' if key == report['retenu'] else '<td></td>'}</tr>"
        )
    return "\n".join(rows)


def write_benchmark_report(
    report: dict,
    html_path: Path,
    *,
    curves: dict[str, dict],
) -> Path:
    roc_test_b64 = _plot_curves(curves, kind="roc", split="test")
    pr_test_b64 = _plot_curves(curves, kind="pr", split="test")
    roc_val_b64 = _plot_curves(curves, kind="roc", split="val")
    pr_val_b64 = _plot_curves(curves, kind="pr", split="val")

    skipped = report.get("skipped") or {}
    skipped_html = (
        "<ul>" + "".join(f"<li><code>{k}</code> : {v}</li>" for k, v in skipped.items()) + "</ul>"
        if skipped
        else "<p>Aucun modèle ignoré.</p>"
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark {report['score']} — CISIA Santé</title>
  <style>
    :root {{ font-family: Inter, system-ui, sans-serif; color: #191c1c; background: #f8faf8; }}
    body {{ margin: 0; padding: 1.5rem; line-height: 1.5; }}
    main {{ max-width: 56rem; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 0.5rem; }}
    .meta {{ color: #404848; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 0.55rem 0.75rem; border-bottom: 1px solid #e1e3e2; text-align: left; font-size: 0.875rem; }}
    th {{ background: #f2f4f3; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .charts {{ display: grid; grid-template-columns: 1fr; gap: 1rem; margin: 1.5rem 0; }}
    @media (min-width: 48rem) {{ .charts {{ grid-template-columns: 1fr 1fr; }} }}
    img {{ width: 100%; height: auto; border: 1px solid #e1e3e2; border-radius: 8px; background: #fff; }}
    code {{ background: #edeeed; padding: 0.1rem 0.35rem; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Benchmark modèles — {report['score']}</h1>
  <p class="meta">
    Train {report['n_train']} · Val {report['n_val']} · Test {report['n_test']} ·
    Modèle retenu : <strong>{report['retenu_label']}</strong> (<code>{report['retenu']}</code>)
  </p>
  <p>{report.get('note', '')}</p>
  <h2>Classement (PR-AUC test)</h2>
  <table>
    <thead>
      <tr>
        <th>Modèle</th><th class="num">PR-AUC</th><th class="num">ROC-AUC</th>
        <th class="num">F2</th><th class="num">Rappel</th><th class="num">Précision</th>
        <th class="num">Seuil</th><th>Retenu</th>
      </tr>
    </thead>
    <tbody>
      {_metrics_table(report)}
    </tbody>
  </table>
  <h2>Modèles ignorés</h2>
  {skipped_html}
  <h2>Courbes</h2>
  <div class="charts">
    <figure><img src="data:image/png;base64,{roc_test_b64}" alt="ROC test"></figure>
    <figure><img src="data:image/png;base64,{pr_test_b64}" alt="PR test"></figure>
    <figure><img src="data:image/png;base64,{roc_val_b64}" alt="ROC validation"></figure>
    <figure><img src="data:image/png;base64,{pr_val_b64}" alt="PR validation"></figure>
  </div>
  <h2>JSON brut</h2>
  <pre style="overflow:auto;font-size:0.75rem;background:#fff;padding:1rem;border-radius:8px;">{json.dumps(report, ensure_ascii=False, indent=2)}</pre>
</main>
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")
    return html_path
