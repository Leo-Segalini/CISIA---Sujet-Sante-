# Notebooks CISIA Santé — Guide de navigation

Données **synthétiques** · démo CIF / jury · jamais une décision clinique réelle.

## Démarrage

```bash
# Tout-en-un (corrige le port Jupyter automatiquement)
./scripts/lance_environnement.sh

# Ou Jupyter seul
source .venv/bin/activate
jupyter notebook notebooks/ --ip=127.0.0.1 --port=8888
```

Ouvrez **http://127.0.0.1:8888/tree** — le dossier `notebooks/` **est le cahier électronique CIF**.

| Livrable CIF | Où |
|--------------|-----|
| Journal de bord (méthode & choix) | `00_guide/02_journal_de_bord.ipynb` |
| Production écrite (données + modèles) | parcours `01_donnees/` → `02_modeles/` |

Parcours conseillé :

0. `00_guide/02_journal_de_bord.ipynb` — **journal de bord**
1. `00_guide/01_cadre_projet.ipynb` — objectifs, cadre RGPD, cohorte
2. `01_donnees/01_inventaire_sources.ipynb` — CSV → DataFrames → colonnes
3. `01_donnees/05_analyse_donnees.ipynb` — nulls, dates hors séjour, patho↔retour
4. `02_modeles/02_nettoyage_donnees.ipynb` — nettoyage
5. `02_modeles/03_preparation_modele.ipynb` — features sortie + télé
6. `02_modeles/04_entrainement_modele.ipynb` — Optuna × 2 scores (30–60 min)
7. `02_modeles/05_lancement_modele.ipynb` — inférence
8. `02_modeles/06_reponse_modele.ipynb` — explication / réponse modèle

> Si la page ne s’ouvre pas : regardez `.run/jupyter.log` ou relancez `./scripts/arrete_environnement.sh` puis `./scripts/lance_environnement.sh`.

---

## Arborescence

```
notebooks/
├── README.md                          ← ce fichier
├── 00_guide/
│   ├── 00_sommaire.ipynb              Index + parcours recommandé
│   ├── 01_cadre_projet.ipynb          Objectifs, cadre RGPD, cohorte
│   └── 02_journal_de_bord.ipynb       ★ Journal méthode & choix (CIF)
├── 01_donnees/                        Pipeline & qualité
│   ├── 01_inventaire_sources.ipynb    ★ Jury : CSV→DF→colonnes→analyses
│   ├── 02_qualite_hallucinations.ipynb  ★ Trous, aberrations, incohérences + graphiques
│   ├── 03_registre_rgpd.ipynb           Sensibilité & usage IA (RGPD)
│   ├── 04_pipeline_donnees.ipynb        Export features curated/
│   └── 05_analyse_donnees.ipynb         ★ Nulls, temporalité, patho↔retour
├── 02_modeles/                          Parcours ML jury + benchmark
│   ├── 01_benchmark_optuna.ipynb        Deep-dive 5 modèles + Optuna
│   ├── 02_nettoyage_donnees.ipynb       ★ Nettoyage
│   ├── 03_preparation_modele.ipynb      ★ Features sortie + télé
│   ├── 04_entrainement_modele.ipynb     ★ Optuna × 2 scores
│   ├── 05_lancement_modele.ipynb        ★ Inférence
│   └── 06_reponse_modele.ipynb          ★ Explication / réponse
├── 03_llm/                              Texte / comptes-rendus
│   └── 01_llm_local_cr.ipynb            Qwen GGUF local
├── _utils/                              Helpers graphiques (ne pas exécuter)
└── _archive/                            Anciens notebooks 01–08 (historique)
```

---

## Extensibilité pipeline (registre)

Les sources et étapes sont déclarées dans `src/data/registry.py` + `pipeline_steps.py`.
**Ajouter un bloc ne nécessite pas de modifier les notebooks** s’ils utilisent le registry.

```python
# Dans un notebook / module d’extension
from src.data.registry import PipelineStep, register_pipeline_step, describe_pipeline

def step_mon_bloc(ctx):
    # ctx.frames / ctx.artifacts / ctx.meta
    ...

register_pipeline_step(PipelineStep(
    id="mon_bloc",
    title="Mon bloc",
    description="Nouvelle étape",
    run=step_mon_bloc,
    phase="features",
))

describe_pipeline()   # le tableau s’enrichit tout seul
```

Nouveau CSV : ajouter une `SourceSpec` dans `SOURCES` (registry) + ligne au registre RGPD.
Vue Jupyter : `from _utils.bootstrap import SOURCES_OVERVIEW, PIPELINE_OVERVIEW`.

---

| # | Notebook | Durée indic. | Objectif |
|---|----------|--------------|----------|
| 1 | `01_donnees/01_inventaire_sources` | 2 min | CSV → DataFrames → colonnes |
| 2 | `02_modeles/02_nettoyage_donnees` | 5 min | Identité, qualité, cohorte |
| 3 | `02_modeles/03_preparation_modele` | 5–10 min | Features sortie + télé → curated |
| 4 | `02_modeles/04_entrainement_modele` | **30–60 min** | Optuna × 2 scores |
| 5 | `02_modeles/05_lancement_modele` | 3 min | Inférence `score_single` |
| 6 | `02_modeles/06_reponse_modele` | 5 min | Facteurs + texte métier |

Optionnel après inventaire : `02_qualite_hallucinations`, `03_registre_rgpd`, `01_benchmark_optuna` (deep-dive).

---

## Hallucinations & incohérences — où c’est documenté ?

Le notebook **`01_donnees/02_qualite_hallucinations.ipynb`** couvre :

| Type | Définition | Exemples dans les données |
|------|------------|---------------------------|
| **Trous** | Valeurs manquantes ou vides | Par colonne, par fichier CSV |
| **Aberrantes** | Hors plage physiologique / biologique | FC > 220, bio hors ref ×2 |
| **Mal notées** | Incohérence métier (« hallucination ») | Durée séjour ≠ dates, TAD ≥ TAS, date acte hors séjour |
| **Sensibilité IA** | Registre RGPD | Usage score sortie / télé par colonne |

Rapport HTML exporté : `data/curated/qualite/rapport_qualite.html`

---

## Équivalent terminal

| Notebook | Commande |
|----------|----------|
| Pipeline données | `PYTHONPATH=. python scripts/run_pipeline.py` |
| Rapport qualité | `PYTHONPATH=. python scripts/run_quality_report.py` |
| Benchmark | `PYTHONPATH=. python scripts/run_benchmark.py --optuna` |
| Déploiement | `PYTHONPATH=. python scripts/train_models.py --optuna` |
| **Prod hôpital** | `PYTHONPATH=. python scripts/promote_production.py` |
| Tout (Docker) | `./scripts/lance_environnement.sh` |

---

## Modèles benchmark (5)

`reference` · `logistic` · `random_forest` · `lightgbm` · `mlp`

Critère : **PR-AUC test** · Seuil : **F2 validation** · Optuna sur RF / LightGBM / MLP.

### Protocoles d’entraînement (comparaison)

```bash
PYTHONPATH=. python scripts/run_training_protocols.py
# → models/protocoles/comparaison_protocoles.csv
```

| Protocole | Rôle |
|-----------|------|
| `holdout_patient` | Déploiement (70/15/15) |
| `cv_patient_k5` | Stabilité (GroupKFold patient) |
| `cv_stratified_patient_k5` | Stabilité + strate prévalence |

---

## Aide

- Spec données : `docs/superpowers/specs/2026-08-24-fondation-donnees-readmission-design.md`
- Spec MLOps : `docs/superpowers/specs/2026-09-01-mlops-retrain-design.md`
- README projet : `../README.md`
