from __future__ import annotations

import html
import unicodedata
from datetime import UTC, datetime

from fpdf import FPDF


def _safe(text: object) -> str:
    """Texte HTML-safe, compatible polices PDF core (latin-1)."""
    raw = str(text if text is not None else "-")
    normalized = unicodedata.normalize("NFKD", raw)
    asciiish = normalized.encode("ascii", "ignore").decode("ascii")
    if not asciiish.strip():
        asciiish = raw
    return html.escape(
        asciiish.replace(" - ", " - ")
        .replace("--", "-")
    )


def build_fiche_pdf(detail: dict) -> bytes:
    """Genere un PDF de fiche sortie."""
    now = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    shap_rows = ""
    for i, fact in enumerate(detail.get("top_shap_global") or [], start=1):
        shap_rows += (
            f"<tr><td>{i}</td><td>{_safe(fact.get('libelle') or fact.get('feature'))}</td>"
            f"<td>{_safe(fact.get('valeur'))}</td>"
            f"<td>{float(fact.get('mean_abs_shap') or 0):.2f}</td></tr>"
        )
    admin = detail.get("admin") or {}
    alerte = "Oui - suivi renforce" if detail.get("alerte_suivi_renforce") else "Non"
    body = f"""
    <h1>CISIA Readmit - Fiche sortie</h1>
    <p><em>Genere le {_safe(now)} - Donnees synthetiques - Usage demo</em></p>
    <hr>
    <h2>Patient</h2>
    <p><b>{_safe(detail.get('NomFamille'))}</b> - {_safe(detail.get('SexeLibelle'))}
    - {_safe(detail.get('age'))} ans
    - {_safe(detail.get('PoidsKg'))} kg</p>
    <p>Sejour <b>{_safe(detail.get('SejourID'))}</b> - {_safe(detail.get('service_libelle'))}</p>
    <h2>Score readmission 30 jours</h2>
    <p style="font-size:18px"><b>{_safe(detail.get('proba_pct'))} %</b>
    (seuil {_safe(detail.get('seuil_pct'))} %) - Alerte : <b>{_safe(alerte)}</b></p>
    <p>Modele : {_safe(detail.get('modele_retenu'))}</p>
    <h2>Facteurs principaux (SHAP)</h2>
    <table border="1" width="100%" cellpadding="4">
    <thead><tr><th>#</th><th>Variable</th><th>Valeur sejour</th><th>|SHAP|</th></tr></thead>
    <tbody>{shap_rows or '<tr><td colspan="4">Non disponible</td></tr>'}</tbody>
    </table>
    <h2>Justification</h2>
    <p>{_safe(detail.get('justification'))}</p>
    <p><small>Source : {_safe(detail.get('justification_backend'))}</small></p>
    <h2>Contexte sejour</h2>
    <ul>
    <li>Admission : {_safe(admin.get('DateAdmission'))}</li>
    <li>Sortie : {_safe(admin.get('DateSortie'))}</li>
    <li>Duree : {_safe(admin.get('DureeSejour'))} j</li>
    <li>Mode sortie : {_safe(admin.get('ModeSortie'))}</li>
    <li>Diagnostics : {_safe(detail.get('n_diag'))}</li>
    <li>Prescriptions : {_safe(detail.get('n_meds'))}</li>
    </ul>
    <hr>
    <p><small>CISIA Sante - IA locale - Ne remplace pas l'avis medical</small></p>
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.write_html(body)
    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1")
