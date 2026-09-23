#!/usr/bin/env python3
"""Améliore Presentation_medical*.pptx : palette Clinical Precision, textes CISIA, transitions."""

from __future__ import annotations

import re
import shutil
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

ROOT = Path(__file__).resolve().parents[1]
PRES = ROOT / "docs" / "presentation"

# Clinical Precision (design system CISIA)
COLOR_MAP = {
    # Presentation_medical (menthe / corail)
    "57C3A7": "003735",
    "F47775": "693B24",
    "507C89": "0D4F4D",
    "44546A": "191C1C",
    "E7E6E6": "F2F4F3",
    "0563C1": "0D4F4D",
    "954F72": "4E2510",
    # Presentation_medical_2 (bleus)
    "1F497D": "003735",
    "EEECE1": "F8FAF8",
    "22AAE4": "0D4F4D",
    "2A81C6": "2D6765",
    "2ECAD7": "86BFBC",
    "CBCBCB": "BFC8C7",
    "576868": "404848",
}

NSMAP = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Contenu principal (deck 1 — widescreen)
SLIDES_MAIN: dict[int, list[str]] = {
    1: [
        "CISIA Santé",
        "Prédiction du risque de réadmission à 30 jours",
        "Solution IA locale · explicable · respectueuse du secret médical",
    ],
    2: [
        "Sommaire — 30 minutes",
        "1. Problème & brief CISIA",
        "2. Solution proposée",
        "3. Construction (données → modèles → produit)",
        "4. Preuves, éthique & limites",
        "5. Démo live",
    ],
    3: [
        "Agenda",
        "Cadrage",
        "Solution",
        "Construction",
        "Preuves",
        "Démo",
    ],
    4: [
        "Équipe & cadre",
        "Léo Segalini Briant",
        "Certification CIF · projet CISIA Santé",
        "Données synthétiques uniquement",
        "Démo 100 % locale (127.0.0.1)",
    ],
    5: [
        "Timeline du projet",
        "Fondation données",
        "Modèle tabulaire",
        "LLM local",
        "Webapp 2 parcours",
        "MLOps & démo jury",
        "2026",
    ],
    6: [
        "Le problème",
        "Qui faut-il suivre dans les 30 jours après la sortie ?",
    ],
    7: [
        "Contexte hospitalier",
        "Sortie à domicile mal anticipée → réadmission évitable",
        "Peu d’outil objectif pour prioriser le suivi",
        "Données de santé = art. 9 RGPD + secret médical",
        "Tout doit rester en local",
    ],
    8: [
        "Brief CISIA — 5 exigences",
        "Prédire le risque 30 j",
        "Qualité / hétérogénéité des données",
        "Mesurer les biais",
        "RGPD & secret médical",
        "Solution opérationnelle",
    ],
    9: [
        "Notre réponse",
        "Score + explication + registre & biais",
        "dans une webapp locale à deux parcours",
    ],
    10: [
        "Vision produit",
        "CISIA Readmit",
        "Prioriser les sorties à risque",
        "Coordonnateur de sortie",
        "Ne remplace pas l’avis médical",
    ],
    11: [
        "Architecture en 4 briques",
        "01",
        "Coffre données",
        "02",
        "Moteur de score",
        "03",
        "Explicabilité",
        "04",
        "Interface",
        "05",
        "Privacy by design",
    ],
    12: [
        "51%",
        "Colonnes autorisées au score",
        "7%",
        "Flag only (biais / audit)",
        "33%",
        "Exclues du score",
        "84%",
        "ROC-AUC LightGBM (test)",
        "61%",
        "PR-AUC (critère de choix)",
        "Indicateurs clés",
        "Registre & modèle",
        "Traçabilité de chaque variable",
        "Sélection honnête sur splits patient-level",
    ],
    13: [
        "Deux parcours UI",
        "Parcours CISIA",
        "Score · SHAP · justification",
        "Biais · registre RGPD",
        "Cœur du brief jury",
        "Démo soignant",
        "Plan d’étages live",
        "Illustration terrain",
        "Secondaire / hors brief",
        "Ne pas mélanger les deux parcours",
        "Le jury évalue d’abord /cisia — le soignant est une preuve d’ancrage.",
    ],
    14: [
        "Parcours jury — 5 étapes",
        "Comprendre",
        "Le modèle",
        "Repérer",
        "Les séjours",
        "Expliquer",
        "Une décision",
    ],
    15: [
        "Démo guidée",
        "Lancer",
        "Puis avancer avec Entrée",
        "À chaque écran",
    ],
    16: [
        "Fiche séjour — ordre d’affichage",
        "Score % + seuil + alerte",
        "Facteurs SHAP",
        "Justification IA locale",
        "CR masqué [PATIENT]",
    ],
    17: [
        "Pipeline de bout en bout",
    ],
    18: [
        "Fondation données",
        "11 CSV + INSEE agrégé contrôlé",
    ],
    19: [
        "Pourquoi une colonne entre-t-elle ?",
        "Arbre de décision données",
        "Identité → exclu",
        "Cible → exclu (fuite)",
        "Post-sortie → exclu score_sortie",
        "Proxy socio → flag only",
        "Clinique justifié → autorisé",
        "Traçabilité registre",
    ],
    20: [
        "Données écartées — exemples",
        "Identité",
        "Cible",
        "Fuite temporelle",
    ],
    21: [
        "Registre chiffré",
        "51",
        "80",
        "50",
        "70",
    ],
    22: [
        "Modèles en compétition",
        "5 algorithmes · mêmes splits patient-level",
        "LightGBM retenu (PR-AUC test)",
        "Seuil choisi par F2 (rappel prioritaire)",
    ],
    23: [
        "01",
        "Référence",
        "03",
        "LightGBM",
        "03",
        "MLP (prudent)",
    ],
    24: [
        "Besoin d’un suivi renforcé ?",
        "Le score alerte — le soignant décide",
    ],
    25: [
        "Résultats LightGBM (test)",
    ],
    26: [
        "Deux scores · deux IA",
    ],
    27: [
        "Stack technique",
    ],
    28: [
        "Biais & transparence",
        "On mesure les écarts (âge, sexe, territoire)",
        "On ne les cache pas",
        "/cisia/biais",
        "Preuve éthique",
    ],
    29: [
        "RGPD",
        "Secret médical",
    ],
    30: [
        "84%",
        "ROC-AUC",
        "61%",
        "PR-AUC",
        "81%",
        "Rappel",
        "71%",
        "F2",
        "Performances test — modèle retenu LightGBM",
    ],
    31: [
        "Limites assumées",
        "Dataset synthétique · n limité",
        "Démo ≠ dispositif médical",
        "LLM = aide à la lecture",
        "Honnêteté = crédibilité",
    ],
    32: [
        "Démo live",
        "Checklist jury",
    ],
    33: [
        "Construction",
    ],
    34: [
        "Apports",
        "Qualité données traçable",
        "Score explicable (SHAP + LLM local)",
        "Produit démo-ready",
        "Privacy by design",
    ],
    35: [
        "Perspectives",
        "Validation clinique",
        "Monitoring biais",
        "Intégration SIH / FHIR",
        "Gouvernance hors démo",
        "Roadmap",
    ],
    36: [
        "Sommaire récap",
        "Prédire",
        "Expliquer",
        "Mesurer",
        "Protéger",
    ],
    37: [
        "Message clé",
        "Prioriser le suivi sans compromettre le secret médical",
        "Local · explicable · mesurable",
        "Données synthétiques",
    ],
    38: [
        "Où retrouver les preuves",
    ],
    39: [
        "Registre",
        "Chaque colonne : sensibilité + usage + pourquoi",
        "Benchmark",
        "Pourquoi LightGBM",
        "Fiche séjour",
        "Pourquoi ce patient",
        "Biais",
        "Écarts affichés",
    ],
    40: [
        "Privacy by design",
        "Bind 127.0.0.1 · LLM local · CR masqués · coffre identité",
        "Aucune donnée patient envoyée au cloud",
    ],
    41: [
        "Avant la démo",
        "Lancer l’environnement local",
        "Ouvrir /cisia/jury",
        "Bouton « Lancer le parcours guidé »",
        "Avancer uniquement avec Entrée",
    ],
    42: [
        "Merci — questions ?",
        "Données fictives · IA locale · ne remplace pas l’avis médical",
    ],
}

# Contenu deck 2 (format 4:3 / plus compact)
SLIDES_ALT: dict[int, list[str]] = {
    1: [
        "CISIA Santé",
        "Prédiction du risque de réadmission à 30 jours",
        "Présentation jury · 30 min · données synthétiques",
    ],
    2: [
        "Agenda",
        "1",
        "2",
        "3",
        "4",
        "5",
        "Problème & brief",
        "Solution produit",
        "Données & choix",
        "Modèles & preuves",
        "Démo & clôture",
    ],
    3: [
        "Cadrage",
        "Pourquoi ce projet ?",
    ],
    4: [
        "Bienvenue",
        "Objectif : prioriser les sorties à domicile nécessitant un suivi renforcé à 30 jours, "
        "avec une IA locale, explicable et conforme au secret médical.",
    ],
    5: [
        "Ce que livre la solution",
        "Score de réadmission 30 j",
        "Explication SHAP + brief LLM",
        "Registre RGPD & audit biais",
        "Webapp démo locale",
    ],
    6: [
        "Acteurs",
        "Coordonnateur sortie",
        "Équipe CISIA / jury",
        "Soignant (illustration)",
        "Patient (données synthétiques)",
    ],
    7: [
        "Timeline",
        "Données",
        "Modèle",
        "LLM",
        "Webapp",
        "Démo",
    ],
    8: [
        "Solution en une phrase",
        "Score tabulaire + explication + registre & biais, webapp locale à 2 parcours.",
    ],
    9: [
        "Parcours CISIA",
        "Le cœur du brief : score, SHAP, justification, biais, registre. Navigation guidée par Entrée.",
    ],
    10: [
        "Parcours soignant",
        "Plan d’étages",
        "Lits live",
        "Constantes",
        "Illustration",
    ],
    11: [
        "Construction données",
        "Inventaire → qualité → registre → features. Chaque colonne a une justification d’usage.",
    ],
    12: [
        "Choix sur les données",
        "Exclure l’identité",
        "Exclure la cible des features",
        "Flaguer les proxies socio",
        "Autoriser le clinique justifié",
    ],
    13: [
        "01",
        "Identité & nominatif",
        "02",
        "Fuite de label / temps",
        "03",
        "Clinique à la sortie",
    ],
    14: [
        "Registre",
        "51 autorisées · 7 flag only · 33 exclues",
    ],
    15: [
        "Modélisation",
        "5 modèles comparés sur les mêmes splits patient-level. Critère : PR-AUC test. Seuil : F2.",
    ],
    16: [
        "LightGBM retenu",
        "ROC-AUC 0,84 · PR-AUC 0,61 · Rappel 0,81 · F2 0,71 · Seuil 0,48",
    ],
    17: [
        "Deux IA distinctes",
        "Tabulaire = % de risque",
        "LLM local = brief texte",
        "Jamais de cloud",
    ],
    18: [
        "Explicabilité",
        "SHAP pour les facteurs",
        "Justification en français",
        "CR masqué [PATIENT]",
    ],
    19: [
        "Biais",
        "Âge · sexe · territoire — écarts mesurés et affichés",
    ],
    20: [
        "Preuves chiffrées",
    ],
    21: [
        "Indicateurs",
        "ROC-AUC",
        "PR-AUC",
        "Rappel",
        "F2",
        "50%",
        "61%",
        "45%",
        "65%",
        "84%",
        "61%",
        "81%",
        "71%",
    ],
    22: [
        "RGPD & local",
        "Registre, coffre identité, bind 127.0.0.1, LLM local.",
    ],
    23: [
        "Limites",
        "70%",
        "Synthétique",
        "20%",
        "Petit n",
        "10%",
        "Hors certification DM",
    ],
    24: [
        "Stack",
        "Python · LightGBM · FastAPI · Docker · Jupyter · SHAP",
    ],
    25: [
        "Démo",
        "/cisia/jury → Lancer → Entrée à chaque étape",
        "Option : /soignant",
    ],
    26: [
        "Récap",
        "Prédire · Expliquer · Mesurer · Protéger",
    ],
    27: [
        "Ancrage territorial",
        "INSEE agrégé (ajout contrôlé)",
        "Pas de socio individuel",
        "Proxies territoire",
    ],
    28: [
        "Sources",
        "Sujet CISIA",
        "INSEE ajouté",
        "Dérivés affichage",
        "25%",
        "35%",
        "55%",
        "10%",
        "Traçabilité origine dans le registre",
    ],
    29: [
        "Prochaines étapes",
    ],
    30: [
        "Perspectives",
    ],
    31: [
        "Merci",
        "Questions ?",
        "Données fictives · IA locale · ne remplace pas l’avis médical",
    ],
    32: [
        "Annexe — icônes A",
        "Redimensionnable sans perte",
        "Couleurs Clinical Precision (#003735)",
        "CISIA Santé",
    ],
    33: [
        "Annexe — icônes B",
        "Redimensionnable sans perte",
        "Couleurs Clinical Precision (#003735)",
        "CISIA Santé",
    ],
    34: [
        "Annexe — icônes C",
        "Redimensionnable sans perte",
        "Couleurs Clinical Precision (#003735)",
        "CISIA Santé",
    ],
}


PLACEHOLDER_REPLACEMENTS = [
    (r"http://www\.free-powerpoint-templates-design\.com", "CISIA Santé"),
    (r"www\.allppt\.com", "CISIA Santé"),
    (r"ALLPPT\.com", "CISIA"),
    (r"ALLPPT Layout", "CISIA Layout"),
    (r"FREE\s*PPT TEMPLATES", "CISIA Santé"),
    (r"Insert the Sub Title of Your Presentation", "Données synthétiques · démo locale"),
    (r"Insert the title of your subtitle Here", "Données synthétiques · démo locale"),
    (r"INSERT THE TITLE\s*OF YOUR PRESENTATION HERE", "Prédiction du risque de réadmission à 30 jours"),
    (r"Insert Your Image", "Capture webapp"),
    (r"Place Your Picture Here", "Capture / schéma"),
    (r"Lorem ipsum[^.]*\.?", "Contenu CISIA — voir notes."),
    (r"LOREM IPSUM[^\n]*", "CISIA SANTÉ"),
    (r"You can simply impress your audience[^.]*\.", "Prioriser le suivi post-sortie grâce à un score explicable."),
    (r"Get a modern PowerPoint\s+Presentation that is beautifully designed\.", "Solution locale, traçable et démontrable pour le jury CIF."),
    (r"Easy to change colors, photos and Text\.?", "Choix documentés dans le registre et les specs."),
    (r"This text can be replaced with your own text", "Contenu projet CISIA Santé."),
    (r"This PowerPoint Template has clean and neutral design[^.]*\.", "Interface Clinical Precision — teal #003735."),
    (r"I hope and I believe that this Template will your Time, Money and Reputation\.", "Chaque décision est justifiée (données, modèles, privacy)."),
    (r"Do you need an online doctor now\?", "Faut-il un suivi renforcé à 30 jours ?"),
    (r"Online\s*Doctor", "Suivi renforcé"),
    (r"ONLINE DIAGNOSIS", "SCORE RÉADMISSION"),
    (r"Power Point Online Diagnosis", "Score de réadmission 30 jours"),
    (r"Awesome\s*Presentation", "Présentation CISIA"),
    (r"AWESOME\s*SLIDE", "POINT CLÉ"),
    (r"AWESOME\s*PRESENTATION", "CISIA SANTÉ"),
    (r"Simple Portfolio Presentation(?: Designed)?", "Parcours produit CISIA"),
    (r"Modern Portfolio Presentation", "Démo produit CISIA"),
    (r"Portfolio Presentation", "Solution CISIA"),
    (r"Infographic Style", "Indicateurs CISIA"),
    (r"Infographic Layout", "Indicateurs CISIA"),
    (r"Agenda Style", "Sommaire"),
    (r"Agenda Layout", "Sommaire"),
    (r"Our Team Style", "Cadre du projet"),
    (r"Our Team Layout", "Acteurs"),
    (r"Our Services", "Livrables"),
    (r"Timeline Style", "Timeline projet"),
    (r"TimeLine Layout", "Timeline projet"),
    (r"Welcome!!", "Contexte"),
    (r"Section Break", "Section"),
    (r"Clean Text Slide\s*for your Presentation", "Message clé pour le jury"),
    (r"Contents(?: Here)?", "Sommaire"),
    (r"CONTENTS", "SOMMAIRE"),
    (r"Name Here", "Rôle projet"),
    (r"Text Here", "Point CISIA"),
    (r"Your Text Here", "Point CISIA"),
    (r"Your Content\s*Here", "Contenu CISIA"),
    (r"Content\s*Here", "Contenu CISIA"),
    (r"Example Text\s*:", "Exemple :"),
    (r"We Create\s*Quality Professional\s*PPT Presentation", "Nous livrons une démo CISIA opérationnelle"),
    (r"We Create\s*Professional Presentation", "Démo CISIA professionnelle"),
    (r"One Column Infographic", "Focus privacy"),
    (r"Column Infographic", "Preuves"),
    (r"Columns Infographic Simple\s+Portfolio Designed", "Arbre de décision données"),
    (r"Columns Layout", "Perspectives"),
    (r"Chart Layout", "Résultats modèle"),
    (r"Table & Chart", "Limites & risques"),
    (r"Table Layout", "Stack & preuves"),
    (r"Worldmap Infographic", "Origine des données"),
    (r"Fully Editable Shapes", "Annexe — formes"),
    (r"Fully Editable Icon Sets:?\s*[ABC]?", "Annexe — icônes"),
    (r"PNG IMAGES", "Captures"),
    (r"EASY TO CHANGE COLORS", "PALETTE CLINICAL PRECISION"),
    (r"Thank You", "Merci"),
    (r"Thank you", "Merci"),
    (r"You can Resize without losing quality", "Redimensionnable sans perte"),
    (r"You can Change Fill Color &\s*Line Color", "Couleurs Clinical Precision (#003735)"),
    (r"With this many slides you are able to make a complete PowerPoint Presentation[^.]*\.", ""),
]


def iter_text_shapes(slide):
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for s in shape.shapes:
                if s.has_text_frame:
                    yield s
        elif shape.has_text_frame:
            yield shape


def shape_full_text(shape) -> str:
    return "\n".join(p.text for p in shape.text_frame.paragraphs)


def set_shape_text(shape, text: str) -> None:
    """Remplace le texte en conservant le format du premier run disponible."""
    tf = shape.text_frame
    paragraphs = list(tf.paragraphs)
    if not paragraphs:
        tf.text = text
        return
    # Clear all but first paragraph
    first = paragraphs[0]
    # Keep first run formatting if any
    if first.runs:
        # Clear extra runs
        first.runs[0].text = text
        for run in first.runs[1:]:
            run.text = ""
    else:
        first.text = text
    # Empty remaining paragraphs
    for p in paragraphs[1:]:
        for run in p.runs:
            run.text = ""
        if not p.runs:
            p.text = ""


def apply_global_replacements(text: str) -> str:
    out = text
    for pattern, repl in PLACEHOLDER_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE | re.DOTALL)
    return out


_PLACEHOLDER_SHAPE = re.compile(
    r"^(Text|Contents?(?: Here)?|Name Here|Your Text Here|Your Content\s*Here|"
    r"Content\s*Here|Text Here|LOREM.*|Insert .+|Easy to change.+|"
    r"You can simply impress.+|Get a modern PowerPoint.+|"
    r"This text can be replaced.+|This PowerPoint Template.+|"
    r"Example Text.*|AWESOME.*|Portfolio Presentation.*|"
    r"Infographic (Style|Layout)|Agenda (Style|Layout)|Our Team.+|"
    r"Our Services|Timeline Style|TimeLine Layout|Welcome!!|"
    r"Section Break|Clean Text Slide.*|ONLINE DIAGNOSIS|"
    r"Power Point Online Diagnosis|Simple Portfolio.+|"
    r"Modern Portfolio Presentation|Columns?.+|Chart Layout|"
    r"Table.+|Worldmap Infographic|Fully Editable.+|PNG IMAGES|"
    r"Thank You|Thank you|FREE\s*PPT TEMPLATES|ALLPPT.*|"
    r"EASY TO CHANGE COLORS|We Create.+|One Column.+|"
    r"Do you need an online doctor now\?|Online\s*Doctor|"
    r"http://.+|www\..+)$",
    re.I | re.S,
)


def _is_placeholder(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _PLACEHOLDER_SHAPE.match(t):
        return True
    if "lorem ipsum" in t.lower():
        return True
    if t.lower() in {"text", "contents", "contents here", "name here"}:
        return True
    return False


def fill_slide(slide, replacements: list[str] | None) -> None:
    shapes = list(iter_text_shapes(slide))
    # First pass: global placeholder cleanup on every text shape
    for shape in shapes:
        original = shape_full_text(shape)
        cleaned = apply_global_replacements(original)
        if cleaned != original:
            set_shape_text(shape, cleaned.strip())

    if not replacements:
        return

    shapes = list(iter_text_shapes(slide))
    targets = []
    for shape in shapes:
        current = shape_full_text(shape).strip()
        if not current:
            continue
        if _is_placeholder(current) or current in {
            "CISIA Santé",
            "Indicateurs CISIA",
            "Sommaire",
            "Solution CISIA",
            "Parcours produit CISIA",
            "Cadre du projet",
            "POINT CLÉ",
            "CISIA SANTÉ",
            "SCORE RÉADMISSION",
            "Suivi renforcé",
            "Présentation CISIA",
            "Message clé pour le jury",
            "CISIA Layout",
            "Capture webapp",
            "Capture / schéma",
            "Annexe — formes",
            "Annexe — icônes",
            "Captures",
            "PALETTE CLINICAL PRECISION",
            "Merci",
            "Données synthétiques · démo locale",
            "Prioriser le suivi post-sortie grâce à un score explicable.",
            "Solution locale, traçable et démontrable pour le jury CIF.",
            "Choix documentés dans le registre et les specs.",
            "Contenu projet CISIA Santé.",
            "Interface Clinical Precision — teal #003735.",
            "Chaque décision est justifiée (données, modèles, privacy).",
            "Faut-il un suivi renforcé à 30 jours ?",
        }:
            targets.append(shape)
        elif len(current) <= 40 and not re.fullmatch(r"\d{4}", current):
            # Short labels (years kept if 4 digits alone handled elsewhere)
            targets.append(shape)

    # Prefer replacing clear placeholders first
    placeholders = [s for s in targets if _is_placeholder(shape_full_text(s)) or shape_full_text(s).strip() in {
        "Text", "Contents", "Contents Here", "Name Here", "Text Here", "Indicateurs CISIA", "Sommaire",
        "Solution CISIA", "Cadre du projet", "POINT CLÉ", "Merci", "CISIA Santé",
        "Données synthétiques · démo locale", "Prioriser le suivi post-sortie grâce à un score explicable.",
        "Solution locale, traçable et démontrable pour le jury CIF.",
        "Choix documentés dans le registre et les specs.",
        "Contenu projet CISIA Santé.",
    }]
    others = [s for s in targets if s not in placeholders]
    ordered = placeholders + others

    for idx, shape in enumerate(ordered):
        if idx >= len(replacements):
            break
        set_shape_text(shape, replacements[idx])


def inject_transitions_and_animations(pptx_path: Path) -> None:
    """Injecte transitions fade + apparitions (appear) via OOXML."""
    tmp = pptx_path.with_suffix(".tmp.pptx")
    with ZipFile(pptx_path, "r") as zin, ZipFile(tmp, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("ppt/theme/theme") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                for old, new in COLOR_MAP.items():
                    text = re.sub(old, new, text, flags=re.IGNORECASE)
                data = text.encode("utf-8")
            elif re.match(r"ppt/slides/slide\d+\.xml$", item.filename):
                data = _enrich_slide_xml(data)
            elif item.filename.endswith(".xml") or item.filename.endswith(".rels"):
                # Also recolor hard-coded srgb in slide layouts / masters
                try:
                    text = data.decode("utf-8")
                    changed = False
                    for old, new in COLOR_MAP.items():
                        if old.lower() in text.lower():
                            text2 = re.sub(old, new, text, flags=re.IGNORECASE)
                            if text2 != text:
                                text = text2
                                changed = True
                    if changed:
                        data = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            zout.writestr(item, data)
    tmp.replace(pptx_path)


def _enrich_slide_xml(data: bytes) -> bytes:
    root = etree.fromstring(data)
    # Remove existing transition/timing
    for tag in ("transition", "timing"):
        for node in root.findall(f"p:{tag}", NSMAP):
            root.remove(node)

    # Transition fade
    transition = etree.SubElement(root, f"{{{NSMAP['p']}}}transition")
    transition.set("spd", "med")
    transition.set("advTm", "0")
    etree.SubElement(transition, f"{{{NSMAP['p']}}}fade")

    # Collect shape ids from spTree
    c_sld = root.find("p:cSld", NSMAP)
    if c_sld is None:
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    sp_tree = c_sld.find("p:spTree", NSMAP)
    shape_ids: list[str] = []
    if sp_tree is not None:
        for sp in sp_tree.findall("p:sp", NSMAP):
            cnv = sp.find("p:nvSpPr/p:cNvPr", NSMAP)
            if cnv is not None and cnv.get("id") and cnv.get("id") != "1":
                # skip id 1 often title placeholder group; still animate text shapes
                shape_ids.append(cnv.get("id"))
        for pic in sp_tree.findall("p:pic", NSMAP):
            cnv = pic.find("p:nvPicPr/p:cNvPr", NSMAP)
            if cnv is not None and cnv.get("id"):
                shape_ids.append(cnv.get("id"))
        for grp in sp_tree.findall("p:grpSp", NSMAP):
            cnv = grp.find("p:nvGrpSpPr/p:cNvPr", NSMAP)
            if cnv is not None and cnv.get("id") and cnv.get("id") not in ("1", "2"):
                shape_ids.append(cnv.get("id"))

    # Limit animations to first 8 shapes to keep clicking reasonable
    shape_ids = shape_ids[:8]
    if not shape_ids:
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    timing = etree.SubElement(root, f"{{{NSMAP['p']}}}timing")
    tn_lst = etree.SubElement(timing, f"{{{NSMAP['p']}}}tnLst")
    par = etree.SubElement(tn_lst, f"{{{NSMAP['p']}}}par")
    c_tn = etree.SubElement(par, f"{{{NSMAP['p']}}}cTn")
    c_tn.set("id", "1")
    c_tn.set("dur", "indefinite")
    c_tn.set("restart", "never")
    c_tn.set("nodeType", "tmRoot")
    child = etree.SubElement(c_tn, f"{{{NSMAP['p']}}}childTnLst")
    seq = etree.SubElement(child, f"{{{NSMAP['p']}}}seq")
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")
    c_tn2 = etree.SubElement(seq, f"{{{NSMAP['p']}}}cTn")
    c_tn2.set("id", "2")
    c_tn2.set("dur", "indefinite")
    c_tn2.set("nodeType", "mainSeq")
    child2 = etree.SubElement(c_tn2, f"{{{NSMAP['p']}}}childTnLst")

    next_id = 3
    for i, sid in enumerate(shape_ids):
        par_i = etree.SubElement(child2, f"{{{NSMAP['p']}}}par")
        c_i = etree.SubElement(par_i, f"{{{NSMAP['p']}}}cTn")
        c_i.set("id", str(next_id))
        next_id += 1
        c_i.set("fill", "hold")
        if i == 0:
            c_i.set("presetID", "1")
            c_i.set("presetClass", "entr")
            c_i.set("presetSubtype", "0")
            c_i.set("grpId", "0")
            c_i.set("nodeType", "clickEffect")
        else:
            c_i.set("presetID", "1")
            c_i.set("presetClass", "entr")
            c_i.set("presetSubtype", "0")
            c_i.set("grpId", "0")
            c_i.set("nodeType", "clickEffect")
        st_cond = etree.SubElement(c_i, f"{{{NSMAP['p']}}}stCondLst")
        cond = etree.SubElement(st_cond, f"{{{NSMAP['p']}}}cond")
        cond.set("delay", "0" if i == 0 else "0")
        child_i = etree.SubElement(c_i, f"{{{NSMAP['p']}}}childTnLst")

        # Set effect
        set_el = etree.SubElement(child_i, f"{{{NSMAP['p']}}}set")
        c_bhvr = etree.SubElement(set_el, f"{{{NSMAP['p']}}}cBhvr")
        c_tn_s = etree.SubElement(c_bhvr, f"{{{NSMAP['p']}}}cTn")
        c_tn_s.set("id", str(next_id))
        next_id += 1
        c_tn_s.set("dur", "1")
        c_tn_s.set("fill", "hold")
        st2 = etree.SubElement(c_tn_s, f"{{{NSMAP['p']}}}stCondLst")
        cond2 = etree.SubElement(st2, f"{{{NSMAP['p']}}}cond")
        cond2.set("delay", "0")
        tgt = etree.SubElement(c_bhvr, f"{{{NSMAP['p']}}}tgtEl")
        sp_tgt = etree.SubElement(tgt, f"{{{NSMAP['p']}}}spTgt")
        sp_tgt.set("spid", sid)
        attr = etree.SubElement(c_bhvr, f"{{{NSMAP['p']}}}attrNameLst")
        attr_n = etree.SubElement(attr, f"{{{NSMAP['p']}}}attrName")
        attr_n.text = "style.visibility"
        to = etree.SubElement(set_el, f"{{{NSMAP['p']}}}to")
        s_str = etree.SubElement(to, f"{{{NSMAP['p']}}}strVal")
        s_str.set("val", "visible")

        # Fade anim
        anim = etree.SubElement(child_i, f"{{{NSMAP['p']}}}animEffect")
        anim.set("transition", "in")
        anim.set("filter", "fade")
        c_bhvr2 = etree.SubElement(anim, f"{{{NSMAP['p']}}}cBhvr")
        c_tn_a = etree.SubElement(c_bhvr2, f"{{{NSMAP['p']}}}cTn")
        c_tn_a.set("id", str(next_id))
        next_id += 1
        c_tn_a.set("dur", "500")
        tgt2 = etree.SubElement(c_bhvr2, f"{{{NSMAP['p']}}}tgtEl")
        sp_tgt2 = etree.SubElement(tgt2, f"{{{NSMAP['p']}}}spTgt")
        sp_tgt2.set("spid", sid)

    # prevCondLst / nextCondLst required by some clients
    prev = etree.SubElement(seq, f"{{{NSMAP['p']}}}prevCondLst")
    pcond = etree.SubElement(prev, f"{{{NSMAP['p']}}}cond")
    pcond.set("evt", "onPrev")
    pcond.set("delay", "0")
    tgt_p = etree.SubElement(pcond, f"{{{NSMAP['p']}}}tgtEl")
    etree.SubElement(tgt_p, f"{{{NSMAP['p']}}}sldTgt")
    nxt = etree.SubElement(seq, f"{{{NSMAP['p']}}}nextCondLst")
    ncond = etree.SubElement(nxt, f"{{{NSMAP['p']}}}cond")
    ncond.set("evt", "onNext")
    ncond.set("delay", "0")
    tgt_n = etree.SubElement(ncond, f"{{{NSMAP['p']}}}tgtEl")
    etree.SubElement(tgt_n, f"{{{NSMAP['p']}}}sldTgt")

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def process(path: Path, slide_map: dict[int, list[str]]) -> None:
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        shutil.copy2(backup, path)
        print(f"Restauré depuis {backup.name}")
    else:
        shutil.copy2(path, backup)
        print(f"Backup → {backup.name}")

    prs = Presentation(str(path))
    for i, slide in enumerate(prs.slides, 1):
        fill_slide(slide, slide_map.get(i))
        print(f"  slide {i}: textes mis à jour")
    prs.save(str(path))
    inject_transitions_and_animations(path)
    print(f"OK {path.name} — couleurs Clinical Precision + transitions fade + apparitions")


def main() -> None:
    process(PRES / "Presentation_medical.pptx", SLIDES_MAIN)
    process(PRES / "Presentation_medical_2.pptx", SLIDES_ALT)


if __name__ == "__main__":
    main()
