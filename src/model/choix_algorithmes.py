"""Choix RF vs HistGB — contenu pédagogique (webapp + notebooks)."""

from __future__ import annotations

from typing import Any


def contenu_choix_modeles() -> dict[str, Any]:
    """Texte structuré : pourquoi RF aujourd’hui, HistGB demain."""
    return {
        "titre": "Choix des modèles — forêt vs gradient boosting",
        "contexte_n": (
            "Sur le jeu CISIA actuel (~480 séjours / ~340 en train), la forêt aléatoire "
            "est le modèle de production pour le score sortie. HistGB est comparé dans le "
            "benchmark et sera préférable dès qu’un plus grand volume de données sera disponible."
        ),
        "decision_actuelle": {
            "modele": "random_forest",
            "libelle": "Forêt aléatoire (Random Forest)",
            "pourquoi": (
                "Avec un petit jeu patient-level, la RF offre le meilleur compromis "
                "PR-AUC / stabilité / interprétabilité (SHAP). Elle surapprend moins qu’un "
                "boosting agressif ou un MLP sur ce volume."
            ),
            "critere": (
                "Classement sur PR-AUC test (classes déséquilibrées) ; seuil d’alerte "
                "choisi pour maximiser le F2 sur validation (priorité au rappel)."
            ),
        },
        "histgb": {
            "role_actuel": (
                "HistGradientBoosting est entraîné dans le catalogue de benchmark "
                "(clé hist_gradient_boosting) pour comparaison honnête sur les mêmes splits, "
                "mais n’est pas le bundle chargé en production CISIA."
            ),
            "pour_grand_jeu": (
                "Pour une mise en production avec un plus grand jeu de données "
                "(plusieurs milliers à dizaines de milliers de séjours), HistGB sera en "
                "général plus efficace : meilleur ratio performance / temps d’entraînement, "
                "meilleure capture des interactions faibles, et meilleure scalabilité mémoire."
            ),
        },
        "rf": {
            "avantages": [
                "Robuste sur petit n et données bruitées (bagging d’arbres).",
                "Bonnes performances PR-AUC sur le jeu CISIA actuel.",
                "Interprétable via importance des variables et SHAP.",
                "Peu de dépendances (sklearn) — déploiement simple.",
                "Moins sensible aux hyperparamètres qu’un boosting finement réglé.",
            ],
            "inconvenients": [
                "Temps et mémoire croissent vite avec n et le nombre d’arbres.",
                "Moins adapté aux très grands volumes que le boosting par histogrammes.",
                "Peut plafonner en performance quand le signal devient riche (grand n).",
            ],
        },
        "histgb_detail": {
            "avantages": [
                "Scalable : entraînement plus rapide / moins gourmand à grand volume.",
                "Souvent meilleur F2 / discrimination dès que n augmente.",
                "Gère bien les interactions non linéaires complexes.",
                "Toujours disponible via sklearn (pas d’obligation LightGBM).",
                "Régularisation (learning rate, L2, early stopping) pour limiter le surapprentissage.",
            ],
            "inconvenients": [
                "Sur petit n : risque de surajustement si mal calibré.",
                "Tuning Optuna plus critique que pour la RF.",
                "Explications SHAP un peu plus coûteuses à calculer.",
                "Sur CISIA actuel : PR-AUC parfois inférieur à la RF malgré un F2 plus haut.",
            ],
        },
        "regle_de_decision": [
            "Petit jeu pédagogique / pilote (~centaines de séjours) → privilégier Random Forest.",
            "Grand jeu production (milliers+) → re-benchmarker ; basculer vers HistGB (ou LightGBM) "
            "si PR-AUC test et stabilité (CV patient) le confirment.",
            "Toujours garder logistic comme baseline interprétable et une calibration + seuil F2.",
            "Ne promouvoir HistGB en prod qu’avec monitoring (drift, calibration) en place.",
        ],
        "protocole_split": {
            "titre": "Protocole train / validation / test",
            "resume": (
                "Non : on n’entraîne pas sur 100 % des données, et on ne teste pas sur 100 %. "
                "Le split est patient-level 70 % / 15 % / 15 % (train / val / test). "
                "Un même patient n’apparaît jamais dans deux jeux (anti-fuite)."
            ),
            "ratios_cibles": {"train": 0.70, "val": 0.15, "test": 0.15},
            "ratios_observes_approx": {
                "train": "~70,8 % (~340 séjours)",
                "val": "~14,2 % (~68 séjours)",
                "test": "~15 % (~72 séjours)",
            },
            "roles": [
                {
                    "jeu": "Train",
                    "role": "Apprentissage des paramètres du modèle (et Optuna).",
                },
                {
                    "jeu": "Validation",
                    "role": "Choix du seuil F2 et tuning hyperparamètres — jamais pour le score final.",
                },
                {
                    "jeu": "Test",
                    "role": "Mesure honnête (PR-AUC, F2) — jamais vu pendant l’entraînement.",
                },
            ],
            "pas_70_30_simple": (
                "Ce n’est pas un simple 70/30 : il y a un jeu de validation dédié (15 %). "
                "Le hold-out total hors train est donc ~30 % (val+test), cohérent avec une "
                "logique 70/30, mais découpé pour caler le seuil sans polluer le test."
            ),
        },
        "unites_constantes": {
            "titre": "Unités des constantes vitales",
            "resume": (
                "Chaque constante a une unité canonique fixe — le modèle n’est pas entraîné "
                "sur un mélange d’unités pour une même mesure (pas de °C et °F mélangés). "
                "En revanche on ne convertit pas toutes les constantes vers « une seule unité » : "
                "FC, SpO₂, tension, température restent des colonnes distinctes, chacune dans "
                "son unité. Le prétraitement normalise par colonne (imputation ; StandardScaler "
                "pour logistic/MLP)."
            ),
            "table": [
                {
                    "mesure": "Fréquence cardiaque",
                    "unite": "bpm (/min)",
                    "source": "signes_vitaux / OC",
                },
                {
                    "mesure": "Tension (sys / dia)",
                    "unite": "mmHg",
                    "source": "signes_vitaux",
                },
                {"mesure": "Température", "unite": "°C", "source": "signes_vitaux"},
                {
                    "mesure": "Fréquence respiratoire",
                    "unite": "/min",
                    "source": "signes_vitaux",
                },
                {"mesure": "SpO₂", "unite": "%", "source": "signes_vitaux / OC"},
                {
                    "mesure": "Poids",
                    "unite": "kg",
                    "source": "objets_connectes + saisie IDE",
                },
            ],
            "biologie": (
                "La biologie est harmonisée vers une unité canonique par panel "
                "(ex. créatinine µmol/L, CRP mg/L) via quality.harmonize_biologie — "
                "pas de mélange d’unités pour un même analyte."
            ),
        },
        "liens": {
            "notebook": "notebooks/02_modeles/04_entrainement_modele.ipynb",
            "manifeste": "models/production_manifest.json",
            "page_web": "/cisia/modeles",
        },
    }
