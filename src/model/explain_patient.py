"""Explications locales du risque de réadmission (SHAP / coefficients)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

from src.web.affichage import format_feature_value, libelle_feature, libelle_sexe
from src.model.train import CategoryToCode, predict_hgb


def _feature_value_display(feat: str, raw: Any) -> str:
    if feat == "Sexe":
        return f"{libelle_sexe(raw)} ({format_feature_value(raw)})"
    return format_feature_value(raw)


def _local_shap_hgb(
    coder: CategoryToCode,
    clf: HistGradientBoostingClassifier,
    X_row: pd.DataFrame,
) -> list[dict[str, Any]]:
    Xt = coder.transform(X_row)
    explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(Xt)
    if isinstance(values, list):
        values = values[1]
    row_vals = np.asarray(values)[0]
    out = []
    for col, shap_val in zip(Xt.columns, row_vals, strict=True):
        raw = X_row[col].iloc[0] if col in X_row.columns else None
        out.append(
            {
                "feature": col,
                "libelle": libelle_feature(col),
                "valeur": _feature_value_display(col, raw),
                "shap": float(shap_val),
                "impact": "hausse" if shap_val > 0 else "baisse",
            }
        )
    out.sort(key=lambda x: abs(x["shap"]), reverse=True)
    return out[:6]


def _local_shap_pipeline(pipe: Pipeline, X_row: pd.DataFrame) -> list[dict[str, Any]]:
    pre = pipe.named_steps["pre"]
    clf = pipe.named_steps["clf"]
    Xt = pre.transform(X_row)
    feature_names = pre.get_feature_names_out()
    explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(Xt)
    if isinstance(values, list):
        values = values[1]
    row_vals = np.asarray(values)[0]
    out = []
    for name, shap_val in zip(feature_names, row_vals, strict=True):
        base = str(name).split("__", 1)[-1]
        match_col = next((c for c in X_row.columns if c in base), base)
        raw = X_row[match_col].iloc[0] if match_col in X_row.columns else None
        out.append(
            {
                "feature": str(match_col),
                "libelle": libelle_feature(str(match_col)),
                "valeur": _feature_value_display(str(match_col), raw),
                "shap": float(shap_val),
                "impact": "hausse" if shap_val > 0 else "baisse",
            }
        )
    out.sort(key=lambda x: abs(x["shap"]), reverse=True)
    seen: set[str] = set()
    deduped = []
    for item in out:
        if item["libelle"] in seen:
            continue
        seen.add(item["libelle"])
        deduped.append(item)
        if len(deduped) >= 6:
            break
    return deduped


def _local_coef_logistic(model: Pipeline, X_row: pd.DataFrame) -> list[dict[str, Any]]:
    pre = model.named_steps["pre"]
    clf = model.named_steps["clf"]
    names = pre.get_feature_names_out()
    Xt = pre.transform(X_row)
    coefs = clf.coef_[0]
    contrib = Xt[0] * coefs
    out = []
    for name, c in zip(names, contrib, strict=True):
        base = name.split("__", 1)[-1]
        raw_col = base.split("_")[0] if base.startswith(tuple(X_row.columns)) else base
        match_col = next((col for col in X_row.columns if col in name), raw_col)
        raw = X_row[match_col].iloc[0] if match_col in X_row.columns else None
        out.append(
            {
                "feature": str(match_col),
                "libelle": libelle_feature(match_col),
                "valeur": _feature_value_display(str(match_col), raw),
                "shap": float(c),
                "impact": "hausse" if c > 0 else "baisse",
            }
        )
    out.sort(key=lambda x: abs(x["shap"]), reverse=True)
    seen: set[str] = set()
    deduped = []
    for item in out:
        if item["libelle"] in seen:
            continue
        seen.add(item["libelle"])
        deduped.append(item)
        if len(deduped) >= 6:
            break
    return deduped


def facteurs_risque_patient(
    *,
    modele: str,
    bundle: dict,
    X_row: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Top facteurs locaux augmentant ou diminuant le risque pour ce séjour."""
    if modele == "hgb" and "coder" in bundle and "hgb" in bundle:
        factors = _local_shap_hgb(bundle["coder"], bundle["hgb"], X_row)
    elif modele in {"random_forest", "lightgbm"} and modele in bundle:
        factors = _local_shap_pipeline(bundle[modele], X_row)
    elif modele == "logistic" and "logistic" in bundle:
        factors = _local_coef_logistic(bundle["logistic"], X_row)
    elif "logistic" in bundle:
        factors = _local_coef_logistic(bundle["logistic"], X_row)
    else:
        factors = []
    max_abs = max((abs(f["shap"]) for f in factors), default=1.0) or 1.0
    for f in factors:
        f["bar_pct"] = round(100.0 * abs(f["shap"]) / max_abs)
    return factors


def build_explication_risque_30j(
    *,
    proba_pct: int,
    seuil_pct: int,
    alerte: bool,
    facteurs: list[dict[str, Any]],
) -> str:
    """Texte lisible : pourquoi ce patient est (ou non) à risque de réadmission."""
    if not facteurs:
        return (
            "Le modèle estime une probabilité de réadmission à 30 jours, "
            "mais les facteurs explicatifs détaillés ne sont pas disponibles."
        )

    hausse = [f for f in facteurs if f["impact"] == "hausse"]
    baisse = [f for f in facteurs if f["impact"] == "baisse"]

    intro = (
        f"Probabilité estimée de réadmission sous 30 jours : {proba_pct} % "
        f"(seuil d’alerte {seuil_pct} %). "
    )
    if alerte:
        intro += "Ce séjour dépasse le seuil : un suivi renforcé à la sortie est recommandé. "
    else:
        intro += "Ce séjour reste sous le seuil d’alerte. "

    parts = [intro.strip()]
    if hausse:
        bullets = "; ".join(
            f"{f['libelle']} ({f['valeur']})" for f in hausse[:3]
        )
        parts.append(f"Éléments qui augmentent le risque : {bullets}.")
    if baisse:
        bullets = "; ".join(
            f"{f['libelle']} ({f['valeur']})" for f in baisse[:2]
        )
        parts.append(f"Éléments qui le diminuent : {bullets}.")
    parts.append(
        "Ces facteurs proviennent du modèle tabulaire (SHAP local ou coefficients) "
        "et ne remplacent pas l’avis clinique."
    )
    return " ".join(parts)
