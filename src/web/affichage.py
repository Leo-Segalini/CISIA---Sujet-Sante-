"""Champs d’affichage soignant : jamais dans le modèle de score."""

from __future__ import annotations

import pandas as pd


def nom_famille(nom_prenom: object) -> str:
    if not isinstance(nom_prenom, str) or not nom_prenom.strip():
        return "—"
    return nom_prenom.strip().split()[0].upper()


def prenom(nom_prenom: object) -> str:
    """Prénom(s) issus du champ vault « NomPrenom » (format « Famille Prénom »)."""
    if not isinstance(nom_prenom, str) or not nom_prenom.strip():
        return "—"
    parts = nom_prenom.strip().split()
    if len(parts) <= 1:
        return "—"
    return " ".join(parts[1:])


def libelle_sexe(sexe: object) -> str:
    s = str(sexe).strip().upper() if sexe is not None and not pd.isna(sexe) else ""
    if s in {"F", "FEMME"}:
        return "Femme"
    if s in {"M", "H", "HOMME"}:
        return "Homme"
    return "Non renseigné"


def pathologies_libelle(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "Aucun antécédent renseigné"
    text = str(raw).strip()
    if not text or text.lower() in {"aucune", "non renseigne", "non renseigné"}:
        return "Aucun antécédent renseigné"
    return text.replace("|", " · ")


_FEATURE_LABELS: dict[str, str] = {
    "Sexe": "Sexe",
    "DureeSejour": "Durée du séjour (j)",
    "TypeSejour": "Type de séjour",
    "n_meds": "Nombre de prescriptions",
    "n_diag": "Nombre de diagnostics",
    "age_admission": "Âge à l’admission",
    "DensiteMedicale": "Densité médicale (territoire)",
    "IndiceDefavorisation": "Indice de défavorisation",
    "PopulationCommune": "Population commune",
    "sv_SpO2_mean": "SpO₂ moyenne",
    "sv_TensionSystolique_mean": "Tension systolique moyenne",
    "sv_FrequenceCardiaque_mean": "Pouls moyen",
    "sv_Temperature_mean": "Température moyenne",
    "sv_FrequenceRespiratoire_mean": "Respiration moyenne",
}


def libelle_feature(name: object) -> str:
    key = str(name)
    if key in _FEATURE_LABELS:
        return _FEATURE_LABELS[key]
    # sv_Xxx_mean → lisible
    if key.startswith("sv_") and key.endswith("_mean"):
        mid = key[3:-5].replace("_", " ")
        return f"{mid} (moyenne)"
    return key.replace("_", " ")


def format_feature_value(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.1f}"
    text = str(value).strip()
    return text if text else "—"
