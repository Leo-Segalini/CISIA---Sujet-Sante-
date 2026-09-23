from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data.paths import CSV_FILES, IDENTITY_COLUMNS, ProjectPaths, get_project_root
from src.data.registre import REGISTRE_COLUMNS

GRAIN_BY_FILE = {
    "patients.csv": "patient",
    "sejours.csv": "sejour",
    "historique.csv": "evenement",
    "diagnostics.csv": "evenement",
    "actes.csv": "evenement",
    "biologies.csv": "evenement",
    "signes_vitaux.csv": "evenement",
    "medications.csv": "evenement",
    "comptes_rendus.csv": "evenement",
    "objets_connectes.csv": "evenement",
    "territoire_insee.csv": "commune",
}

KEYS = {
    "PatientID",
    "SejourID",
    "EvenementID",
    "DiagnosticID",
    "ActeID",
    "BiologieID",
    "ConstanteID",
    "PrescriptionID",
    "CompteRenduID",
    "MesureID",
}


def classify(fichier: str, colonne: str) -> dict[str, str]:
    if colonne in IDENTITY_COLUMNS:
        return {
            "categorie": "identite",
            "sensibilite": "identite_directe",
            "usage_score_sortie": "exclu",
            "usage_score_tele": "exclu",
            "justification_hopital": "",
            "risque_principal": "secret_medical",
            "regle_nettoyage": "coffre identité ; jamais dans curated",
        }
    if colonne == "MedecinTraitant":
        return {
            "categorie": "identite",
            "sensibilite": "faible",
            "usage_score_sortie": "exclu",
            "usage_score_tele": "exclu",
            "justification_hopital": "",
            "risque_principal": "biais",
            "regle_nettoyage": "audit seulement ; risque de réidentification",
        }
    if colonne == "Readmission30j":
        return {
            "categorie": "cible",
            "sensibilite": "aucune",
            "usage_score_sortie": "exclu",
            "usage_score_tele": "exclu",
            "justification_hopital": "",
            "risque_principal": "fuite",
            "regle_nettoyage": "cible uniquement, jamais feature",
        }
    if colonne in KEYS:
        return {
            "categorie": "parcours",
            "sensibilite": "faible",
            "usage_score_sortie": "exclu",
            "usage_score_tele": "exclu",
            "justification_hopital": "",
            "risque_principal": "none",
            "regle_nettoyage": "clé technique ; jointe puis retirée des features sauf SejourID/PatientID exposés comme clés",
        }
    if fichier == "territoire_insee.csv" and colonne in {
        "IndiceDefavorisation",
        "DensiteMedicale",
        "PopulationCommune",
    }:
        return {
            "categorie": "territoire",
            "sensibilite": "proxy_socio",
            "usage_score_sortie": "autorise",
            "usage_score_tele": "autorise",
            "justification_hopital": "Proxy territorial agrégé pour cibler l'accompagnement en désert médical, sans donnée socio-éco individuelle.",
            "risque_principal": "biais",
            "regle_nettoyage": "jointure Commune+CodePostal ; flag territoire_inconnu",
        }
    if fichier == "objets_connectes.csv" and colonne in {"Horodatage", "TypeMesure", "Valeur", "QualiteSignal"}:
        return {
            "categorie": "capteur",
            "sensibilite": "sante_art9",
            "usage_score_sortie": "exclu",
            "usage_score_tele": "autorise",
            "justification_hopital": "Télésurveillance post-sortie pour ajuster le suivi à domicile.",
            "risque_principal": "fuite",
            "regle_nettoyage": "uniquement QualiteSignal=Bon ; fenêtre fixe post-sortie",
        }
    if colonne in {"RegimeAssurance", "SituationFamiliale"}:
        return {
            "categorie": "parcours",
            "sensibilite": "proxy_socio",
            "usage_score_sortie": "flag_only",
            "usage_score_tele": "flag_only",
            "justification_hopital": "",
            "risque_principal": "biais",
            "regle_nettoyage": "descriptif et biais ; hors scores tant que non justifié opérationnellement",
        }
    if fichier == "comptes_rendus.csv" and colonne == "TexteCR":
        return {
            "categorie": "texte",
            "sensibilite": "sante_art9",
            "usage_score_sortie": "flag_only",
            "usage_score_tele": "flag_only",
            "justification_hopital": "",
            "risque_principal": "secret_medical",
            "regle_nettoyage": "masquage nominatif ; LLM local ultérieur ; pas de feature brute dans ce chantier",
        }

    # Clinique / parcours par défaut
    justif = "Signal clinique ou de parcours pour alerter les équipes à la sortie et prioriser le suivi."
    return {
        "categorie": "clinique" if fichier != "historique.csv" else "parcours",
        "sensibilite": "sante_art9",
        "usage_score_sortie": "autorise",
        "usage_score_tele": "autorise",
        "justification_hopital": justif,
        "risque_principal": "qualite",
        "regle_nettoyage": "cutoff DateSortie ; flags qualité ; pas d'imputation silencieuse",
    }


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    paths.ensure_data_dirs()
    rows = []
    for name in CSV_FILES:
        df = pd.read_csv(paths.csv_sources / name, nrows=0)
        for col in df.columns:
            meta = classify(name, col)
            rows.append(
                {
                    "fichier_source": name,
                    "colonne": col,
                    "grain": GRAIN_BY_FILE[name],
                    "origine_donnee": "sujet",
                    **meta,
                }
            )
    # Compléments INSEE (fichier séparé, hors sujet)
    insee_cols = [
        (
            "INSEE_ajoute_CodeCommune",
            "flag_only",
            "faible",
            "Code Officiel Géographique ; jointure territoriale, hors score ML actuel.",
        ),
        (
            "INSEE_ajoute_PopulationLegale",
            "autorise",
            "proxy_socio",
            "Population légale INSEE (agrégée) pour contextualiser le territoire, distincte de PopulationCommune du sujet.",
        ),
        (
            "INSEE_ajoute_PartPlus65Ans_pct",
            "autorise",
            "proxy_socio",
            "Part des 65 ans et plus (INSEE, agrégée) : proxy de vieillissement territorial pour cibler l'accompagnement.",
        ),
        (
            "INSEE_ajoute_Departement",
            "flag_only",
            "faible",
            "Libellé département INSEE ; descriptif.",
        ),
        (
            "INSEE_ajoute_Region",
            "flag_only",
            "faible",
            "Libellé région INSEE ; descriptif.",
        ),
        (
            "INSEE_ajoute_EcartPop_vs_sujet",
            "flag_only",
            "faible",
            "Écart PopulationCommune (sujet) − population INSEE : audit qualité pédagogique.",
        ),
        (
            "INSEE_ajoute_Millesime",
            "exclu",
            "aucune",
            "",
        ),
    ]
    for col, usage, sens, justif in insee_cols:
        rows.append(
            {
                "fichier_source": "territoire_insee_complements.csv",
                "colonne": col,
                "grain": "commune",
                "categorie": "territoire",
                "sensibilite": sens,
                "usage_score_sortie": usage,
                "usage_score_tele": usage,
                "justification_hopital": justif,
                "risque_principal": "biais" if sens == "proxy_socio" else "qualite",
                "regle_nettoyage": "fichier data/external/ ; préfixe INSEE_ajoute_ ; sujet non modifié",
                "origine_donnee": "insee_ajoute",
            }
        )
    for col, sens, usage, justif in [
        ("NomFamille", "identite_directe", "exclu", ""),
        ("Etage", "faible", "exclu", ""),
        ("Chambre", "faible", "exclu", ""),
        ("Lit", "faible", "exclu", ""),
    ]:
        rows.append(
            {
                "fichier_source": "affichage_soignant",
                "colonne": col,
                "grain": "sejour",
                "categorie": "identite" if col == "NomFamille" else "parcours",
                "sensibilite": sens,
                "usage_score_sortie": usage,
                "usage_score_tele": usage,
                "justification_hopital": justif,
                "risque_principal": "secret_medical" if col == "NomFamille" else "none",
                "regle_nettoyage": (
                    "Nom de famille seul dérivé de NomPrenom pour l’écran soignant ; exclu du score ML"
                    if col == "NomFamille"
                    else "Localisation fictive stable pour la démo hôpital ; hors CSV sujet"
                ),
                "origine_donnee": "derive_affichage",
            }
        )
    out = pd.DataFrame(rows, columns=REGISTRE_COLUMNS)
    dest = paths.registres / "registre_colonnes.csv"
    out.to_csv(dest, index=False)
    print(f"écrit {dest} ({len(out)} colonnes)")


if __name__ == "__main__":
    main()
