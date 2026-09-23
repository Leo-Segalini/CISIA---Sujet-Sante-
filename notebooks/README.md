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

Ouvrez **http://127.0.0.1:8888/tree** puis **parcours jury DS** :

1. `01_donnees/01_inventaire_sources.ipynb` — CSV → DataFrames → colonnes
2. `02_modeles/02_nettoyage_donnees.ipynb` — nettoyage
3. `02_modeles/03_preparation_modele.ipynb` — features sortie + télé
4. `02_modeles/04_entrainement_modele.ipynb` — Optuna × 2 scores (30–60 min)
5. `02_modeles/05_lancement_modele.ipynb` — inférence
6. `02_modeles/06_reponse_modele.ipynb` — explication / réponse modèle

> Si la page ne s’ouvre pas : regardez `.run/jupyter.log` ou relancez `./scripts/arrete_environnement.sh` puis `./scripts/lance_environnement.sh`.

---

## Arborescence

```
notebooks/
├── README.md                          ← ce fichier
├── 00_guide/
│   └── 00_sommaire.ipynb              Index + parcours recommandé
├── 01_donnees/                        Pipeline & qualité
│   ├── 01_inventaire_sources.ipynb    ★ Jury : CSV→DF→colonnes→analyses
│   ├── 02_qualite_hallucinations.ipynb  ★ Trous, aberrations, incohérences + graphiques
│   ├── 03_registre_rgpd.ipynb           Sensibilité & usage IA (RGPD)
│   └── 04_pipeline_donnees.ipynb        Export features curated/
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

## Parcours recommandé (Run All dans l’ordre)

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
| Tout (Docker) | `./scripts/lance_environnement.sh` |

---

## Modèles benchmark (5)

`reference` · `logistic` · `random_forest` · `lightgbm` · `mlp`

Critère : **PR-AUC test** · Seuil : **F2 validation** · Optuna sur RF / LightGBM / MLP.

---

## Aide

- Spec données : `docs/superpowers/specs/2026-08-24-fondation-donnees-readmission-design.md`
- Spec MLOps : `docs/superpowers/specs/2026-09-01-mlops-retrain-design.md`
- README projet : `../README.md`
