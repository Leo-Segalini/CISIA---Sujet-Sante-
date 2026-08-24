# Fondation données — Réadmission 30j — Plan d’implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produire un pipeline local traçable (registre colonne par colonne, qualité, double score) qui exporte `features_score_sortie.parquet` et `features_score_tele.parquet` sans nominatif ni fuite temporelle.

**Architecture:** Copies CSV → coffre identité + tables pseudonymisées → contrôles qualité versionnés dans `src/data/` → registre machine-lisible → cohorte `Domicile` + split patient → agrégats features cutoff-aware → parquets `data/curated/`. Cinq notebooks racontent et exécutent le flux ; pytest verrouille les règles anti-fuite.

**Tech Stack:** Python ≥ 3.11, pandas, pyarrow, pytest, Jupyter, pathlib. Aucune API cloud. Aucun entraînement ML/LLM dans ce plan.

**Spec de référence :** `docs/superpowers/specs/2026-08-24-fondation-donnees-readmission-design.md`

## Global Constraints

- Sources = uniquement les 11 CSV du sujet (racine projet) ; aucun enrichissement externe.
- 100 % local ; aucun appel réseau dans le code de ce chantier.
- Nominatif (`NomPrenom`, `PersonneAPrevenir`) hors ML et hors `data/curated/`.
- Cohorte ML : `ModeSortie == "Domicile"` uniquement.
- Deux scores distincts ; objets connectés exclus du score sortie.
- Split train/val/test **par PatientID**.
- `Readmission30j` jamais utilisée comme feature.
- `justification_hopital` obligatoire si `autorise` et sensibilité ∈ {identite_directe, sante_art9, proxy_socio}.
- `.gitignore` : `data/raw/`, `data/vault_identite/`, `data/pseudonymise/`, `data/curated/`.
- Commits fréquents ; messages en français ou conventional commits clairs ; ne committer que si l’utilisateur l’autorise explicitement dans la session d’exécution (sinon stopper avant `git commit` et demander).

---

## Cartographie des fichiers

| Fichier | Responsabilité |
|---|---|
| `requirements.txt` | Dépendances figées (pandas, pyarrow, pytest, jupyter, openpyxl optionnel non requis) |
| `.gitignore` | Exclure données et caches |
| `src/__init__.py` | Package |
| `src/data/__init__.py` | Package data |
| `src/data/paths.py` | Chemins racine / raw / vault / pseudo / curated |
| `src/data/load.py` | Copie raw + lecture CSV |
| `src/data/identity.py` | Séparation coffre / pseudonymisation patients |
| `src/data/quality.py` | Durées, plages physiologiques, biologie, capteurs |
| `src/data/cohort.py` | Filtre Domicile, split patient |
| `src/data/features_sortie.py` | Features score sortie (cutoff DateSortie) |
| `src/data/features_tele.py` | Features score télé (fenêtre fixe post-sortie) |
| `src/data/registre.py` | Lecture/validation couverture registre |
| `docs/registres/registre_colonnes.csv` | Métadonnées colonnes (sans lignes patients) |
| `notebooks/01_…05_….ipynb` | Récit + exécution |
| `tests/test_*.py` | Règles bloquantes |
| `scripts/run_pipeline.py` | Orchestration CLI hors notebook (optionnelle mais utile) |

---

### Task 1: Scaffolding projet (gitignore, requirements, arborescence)

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `src/data/__init__.py`
- Create: `src/data/paths.py`
- Create: `tests/__init__.py`
- Create: `data/raw/.gitkeep` (ignoré ensuite — préférer README locaux non versionnés : créer les dossiers via code)
- Create: `README.md` (périmètre fondation + lien spec)

**Interfaces:**
- Produces: `ProjectPaths` dataclass avec attributs `root`, `raw`, `vault`, `pseudonymise`, `curated`, `registres`, `csv_sources`

- [ ] **Step 1: Écrire `src/data/paths.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CSV_FILES = (
    "patients.csv",
    "sejours.csv",
    "historique.csv",
    "diagnostics.csv",
    "actes.csv",
    "biologies.csv",
    "signes_vitaux.csv",
    "medications.csv",
    "comptes_rendus.csv",
    "objets_connectes.csv",
    "territoire_insee.csv",
)

IDENTITY_COLUMNS = ("NomPrenom", "PersonneAPrevenir")


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def vault(self) -> Path:
        return self.root / "data" / "vault_identite"

    @property
    def pseudonymise(self) -> Path:
        return self.root / "data" / "pseudonymise"

    @property
    def curated(self) -> Path:
        return self.root / "data" / "curated"

    @property
    def registres(self) -> Path:
        return self.root / "docs" / "registres"

    @property
    def csv_sources(self) -> Path:
        """CSV pédagogiques fournis à la racine du sujet."""
        return self.root

    def ensure_data_dirs(self) -> None:
        for p in (self.raw, self.vault, self.pseudonymise, self.curated, self.registres):
            p.mkdir(parents=True, exist_ok=True)


def get_project_root() -> Path:
    """Remonte jusqu'au dossier contenant Sujet.md et patients.csv."""
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "Sujet.md").exists() and (candidate / "patients.csv").exists():
            return candidate
    raise FileNotFoundError("Racine projet introuvable (Sujet.md + patients.csv).")
```

- [ ] **Step 2: Écrire `requirements.txt`**

```text
pandas>=2.2,<3
pyarrow>=16,<22
pytest>=8,<9
jupyter>=1.0,<2
notebook>=7,<8
```

- [ ] **Step 3: Écrire `.gitignore`**

```text
__pycache__/
*.py[cod]
.pytest_cache/
.ipynb_checkpoints/
.venv/
venv/
.env
data/raw/
data/vault_identite/
data/pseudonymise/
data/curated/
*.parquet
.DS_Store
```

- [ ] **Step 4: Écrire test des chemins**

Create: `tests/test_paths.py`

```python
from src.data.paths import CSV_FILES, ProjectPaths, get_project_root


def test_project_root_contains_sources():
    root = get_project_root()
    assert (root / "patients.csv").exists()
    assert (root / "sejours.csv").exists()


def test_ensure_data_dirs_creates_tree(tmp_path):
    # Utilise une racine temporaire + fichiers minimaux
    (tmp_path / "Sujet.md").write_text("x", encoding="utf-8")
    (tmp_path / "patients.csv").write_text("PatientID\n", encoding="utf-8")
    paths = ProjectPaths(root=tmp_path)
    paths.ensure_data_dirs()
    assert paths.raw.is_dir()
    assert paths.vault.is_dir()
    assert paths.pseudonymise.is_dir()
    assert paths.curated.is_dir()
    assert len(CSV_FILES) == 11
```

- [ ] **Step 5: Créer venv, installer, lancer pytest**

```bash
cd "/Users/segalini-briant/Documents/GitHub/CISIA - Sujet Santé"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/test_paths.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: README minimal**

Create: `README.md` — expliquer le chantier fondation, lien vers la spec, commande pytest, rappel « données hors git / synthétiques ».

- [ ] **Step 7: Commit uniquement si l’utilisateur l’autorise**

```bash
git add requirements.txt .gitignore src tests/test_paths.py README.md
git status
# Demander avant commit
```

---

### Task 2: Chargement raw + séparation identité / pseudonyme

**Files:**
- Create: `src/data/load.py`
- Create: `src/data/identity.py`
- Create: `tests/test_identity.py`

**Interfaces:**
- Consumes: `ProjectPaths`, `CSV_FILES`, `IDENTITY_COLUMNS`
- Produces:
  - `copy_sources_to_raw(paths: ProjectPaths) -> dict[str, Path]`
  - `load_csv(paths: ProjectPaths, name: str, *, from_raw: bool = True) -> pd.DataFrame`
  - `split_identity_and_pseudonymise(patients: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
  - `persist_identity_split(paths: ProjectPaths, vault: pd.DataFrame, patients_pseudo: pd.DataFrame) -> None`

- [ ] **Step 1: Test qui échoue — nominatif hors table pseudonymisée**

```python
import pandas as pd
from src.data.identity import split_identity_and_pseudonymise


def test_split_moves_identity_columns():
    patients = pd.DataFrame(
        {
            "PatientID": ["PAT-1"],
            "NomPrenom": ["Dupont Alice"],
            "PersonneAPrevenir": ["Fils"],
            "Sexe": ["F"],
            "CodePostal": ["75001"],
        }
    )
    vault, pseudo = split_identity_and_pseudonymise(patients)
    assert list(vault.columns) == ["PatientID", "NomPrenom", "PersonneAPrevenir"]
    assert "NomPrenom" not in pseudo.columns
    assert "PersonneAPrevenir" not in pseudo.columns
    assert pseudo.loc[0, "Sexe"] == "F"
```

- [ ] **Step 2: Run test — FAIL (module absent)**

```bash
PYTHONPATH=. pytest tests/test_identity.py::test_split_moves_identity_columns -v
```

- [ ] **Step 3: Implémenter `identity.py` et `load.py`**

`src/data/load.py` :

```python
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.data.paths import CSV_FILES, ProjectPaths


def copy_sources_to_raw(paths: ProjectPaths) -> dict[str, Path]:
    paths.ensure_data_dirs()
    out: dict[str, Path] = {}
    missing: list[str] = []
    for name in CSV_FILES:
        src = paths.csv_sources / name
        if not src.exists():
            missing.append(name)
            continue
        dest = paths.raw / name
        shutil.copy2(src, dest)
        out[name] = dest
    if missing:
        raise FileNotFoundError(f"CSV manquants à la racine: {missing}")
    return out


def load_csv(paths: ProjectPaths, name: str, *, from_raw: bool = True) -> pd.DataFrame:
    base = paths.raw if from_raw else paths.csv_sources
    path = base / name
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    return pd.read_csv(path)
```

`src/data/identity.py` :

```python
from __future__ import annotations

import pandas as pd

from src.data.paths import IDENTITY_COLUMNS, ProjectPaths


def split_identity_and_pseudonymise(
    patients: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [c for c in IDENTITY_COLUMNS if c not in patients.columns]
    if missing:
        raise KeyError(f"Colonnes identité absentes: {missing}")
    if "PatientID" not in patients.columns:
        raise KeyError("PatientID manquant")
    vault = patients[["PatientID", *IDENTITY_COLUMNS]].copy()
    pseudo = patients.drop(columns=list(IDENTITY_COLUMNS)).copy()
    return vault, pseudo


def persist_identity_split(
    paths: ProjectPaths,
    vault: pd.DataFrame,
    patients_pseudo: pd.DataFrame,
) -> None:
    paths.ensure_data_dirs()
    vault.to_csv(paths.vault / "patients_identite.csv", index=False)
    patients_pseudo.to_csv(paths.pseudonymise / "patients.csv", index=False)
```

- [ ] **Step 4: Pytest PASS + test d’intégration copie raw**

Ajouter dans `tests/test_identity.py` :

```python
from src.data.load import copy_sources_to_raw, load_csv
from src.data.paths import ProjectPaths, get_project_root
from src.data.identity import split_identity_and_pseudonymise, persist_identity_split


def test_copy_and_persist_real_sources(tmp_path):
    root = get_project_root()
    # Pointer raw/vault/pseudo vers tmp tout en lisant les CSV sources du vrai root
    paths = ProjectPaths(root=root)
    # Pour ne pas polluer: on copie dans un ProjectPaths custom
    class TmpPaths(ProjectPaths):
        pass

    tp = ProjectPaths(root=tmp_path)
    (tmp_path / "Sujet.md").write_text("x", encoding="utf-8")
    import shutil
    for name in ["patients.csv"]:
        shutil.copy2(root / name, tmp_path / name)
    # Minimal: tester split sur patients réels
    patients = load_csv(ProjectPaths(root=root), "patients.csv", from_raw=False)
    vault, pseudo = split_identity_and_pseudonymise(patients)
    persist_identity_split(tp, vault, pseudo)
    assert (tp.vault / "patients_identite.csv").exists()
    reloaded = pd.read_csv(tp.pseudonymise / "patients.csv")
    assert "NomPrenom" not in reloaded.columns
```

```bash
PYTHONPATH=. pytest tests/test_identity.py -v
```

Expected: PASS.

---

### Task 3: Règles qualité — durées et plages physiologiques

**Files:**
- Create: `src/data/quality.py`
- Create: `tests/test_quality.py`

**Interfaces:**
- Produces:
  - `PHYSIO_RANGES: dict[str, tuple[float, float]]`
  - `recalculate_duree_sejour(sejours: pd.DataFrame) -> pd.DataFrame`  
    Colonnes ajoutées : `DureeSejour_brute`, `DureeSejour`, `flag_duree_incoherente` (bool)
  - `flag_out_of_range(df: pd.DataFrame, column: str, low: float, high: float, flag_name: str) -> pd.DataFrame`
  - `harmonize_biologie(biologies: pd.DataFrame) -> pd.DataFrame`  
    Ajoute `Valeur_canonique`, `Unite_canonique`, `flag_biologie_aberrante`
  - `filter_objets_connectes_bons(oc: pd.DataFrame) -> pd.DataFrame`

**Plages physiologiques (figées dans le code, justifiées dans notebook 02) :**

| Colonne | Min | Max |
|---|---|---|
| FrequenceCardiaque | 30 | 220 |
| TensionSystolique | 60 | 250 |
| TensionDiastolique | 30 | 150 |
| Temperature | 34.0 | 42.0 |
| FrequenceRespiratoire | 5 | 60 |
| SpO2 | 50 | 100 |

- [ ] **Step 1: Tests qui échouent**

```python
import pandas as pd
from src.data.quality import recalculate_duree_sejour, filter_objets_connectes_bons


def test_recalculate_negative_duree():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "DateAdmission": ["2024-01-10 10:00:00"],
            "DateSortie": ["2024-01-12 10:00:00"],
            "DureeSejour": [-3],
        }
    )
    out = recalculate_duree_sejour(sejours)
    assert out.loc[0, "DureeSejour_brute"] == -3
    assert out.loc[0, "DureeSejour"] == 2
    assert bool(out.loc[0, "flag_duree_incoherente"]) is True


def test_objets_connectes_bons_only():
    oc = pd.DataFrame(
        {
            "MesureID": [1, 2, 3],
            "QualiteSignal": ["Bon", "Gap", "CapteurDefaillant"],
            "Valeur": [1.0, 2.0, 3.0],
        }
    )
    out = filter_objets_connectes_bons(oc)
    assert len(out) == 1
    assert out.iloc[0]["QualiteSignal"] == "Bon"
```

- [ ] **Step 2: Pytest FAIL puis implémenter `quality.py`**

```python
from __future__ import annotations

import pandas as pd

PHYSIO_RANGES: dict[str, tuple[float, float]] = {
    "FrequenceCardiaque": (30, 220),
    "TensionSystolique": (60, 250),
    "TensionDiastolique": (30, 150),
    "Temperature": (34.0, 42.0),
    "FrequenceRespiratoire": (5, 60),
    "SpO2": (50, 100),
}

# Unités canoniques par panel (biologie)
BIO_CANONICAL_UNIT = {
    "Hemoglobine": "g/dL",
    "Creatinine": "umol/L",
    "CRP": "mg/L",
    "Natremie": "mmol/L",
    "GlobulesBlancs": "G/L",
}


def recalculate_duree_sejour(sejours: pd.DataFrame) -> pd.DataFrame:
    out = sejours.copy()
    out["DureeSejour_brute"] = out["DureeSejour"]
    admission = pd.to_datetime(out["DateAdmission"], errors="coerce")
    sortie = pd.to_datetime(out["DateSortie"], errors="coerce")
    computed = (sortie - admission).dt.total_seconds() / 86400.0
    computed_days = computed.round().astype("Int64")
    brute = pd.to_numeric(out["DureeSejour_brute"], errors="coerce")
    incoherent = brute.isna() | (brute < 0) | ((brute - computed_days).abs() > 1)
    out["flag_duree_incoherente"] = incoherent.fillna(True)
    out["DureeSejour"] = brute.where(~out["flag_duree_incoherente"], computed_days)
    return out


def flag_out_of_range(
    df: pd.DataFrame, column: str, low: float, high: float, flag_name: str
) -> pd.DataFrame:
    out = df.copy()
    vals = pd.to_numeric(out[column], errors="coerce")
    out[flag_name] = vals.isna() | (vals < low) | (vals > high)
    return out


def filter_objets_connectes_bons(oc: pd.DataFrame) -> pd.DataFrame:
    return oc.loc[oc["QualiteSignal"] == "Bon"].copy()


def harmonize_biologie(biologies: pd.DataFrame) -> pd.DataFrame:
    """Version minimale: copie valeur + flag hors bornes de référence ; unité canonique déclarée."""
    out = biologies.copy()
    out["Unite_canonique"] = out["Panel"].map(BIO_CANONICAL_UNIT)
    out["Valeur_canonique"] = pd.to_numeric(out["Valeur"], errors="coerce")
    bas = pd.to_numeric(out["ValeurReferenceBas"], errors="coerce")
    haut = pd.to_numeric(out["ValeurReferenceHaut"], errors="coerce")
    # Aberrant si hors référence *élargie* (×0.5 / ×2) ou NaN
    out["flag_biologie_aberrante"] = (
        out["Valeur_canonique"].isna()
        | (out["Valeur_canonique"] < bas * 0.5)
        | (out["Valeur_canonique"] > haut * 2.0)
    )
    return out
```

- [ ] **Step 3: Pytest PASS**

```bash
PYTHONPATH=. pytest tests/test_quality.py -v
```

---

### Task 4: Cohorte Domicile + split patient

**Files:**
- Create: `src/data/cohort.py`
- Create: `tests/test_cohort.py`

**Interfaces:**
- Produces:
  - `filter_domicile(sejours: pd.DataFrame) -> pd.DataFrame`
  - `patient_level_split(sejours: pd.DataFrame, *, seed: int = 42, ratios=(0.7, 0.15, 0.15)) -> pd.DataFrame`  
    Ajoute colonne `split` ∈ {`train`,`val`,`test`} ; tous les séjours d’un même `PatientID` partagent le même split.

- [ ] **Step 1: Tests**

```python
import pandas as pd
from src.data.cohort import filter_domicile, patient_level_split


def test_filter_domicile_only():
    s = pd.DataFrame(
        {
            "SejourID": ["a", "b", "c"],
            "PatientID": ["p1", "p2", "p3"],
            "ModeSortie": ["Domicile", "Deces", "EHPAD"],
        }
    )
    out = filter_domicile(s)
    assert list(out["SejourID"]) == ["a"]


def test_patient_level_split_no_leakage():
    s = pd.DataFrame(
        {
            "SejourID": ["s1", "s2", "s3", "s4"],
            "PatientID": ["p1", "p1", "p2", "p3"],
            "ModeSortie": ["Domicile"] * 4,
        }
    )
    out = patient_level_split(s, seed=0)
    by_patient = out.groupby("PatientID")["split"].nunique()
    assert (by_patient == 1).all()
    assert set(out["split"]).issubset({"train", "val", "test"})
```

- [ ] **Step 2: Implémenter**

```python
from __future__ import annotations

import numpy as np
import pandas as pd


def filter_domicile(sejours: pd.DataFrame) -> pd.DataFrame:
    if "ModeSortie" not in sejours.columns:
        raise KeyError("ModeSortie manquant")
    return sejours.loc[sejours["ModeSortie"] == "Domicile"].copy()


def patient_level_split(
    sejours: pd.DataFrame,
    *,
    seed: int = 42,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> pd.DataFrame:
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError("ratios must sum to 1")
    out = sejours.copy()
    patients = out["PatientID"].drop_duplicates().sort_values().to_numpy()
    rng = np.random.default_rng(seed)
    rng.shuffle(patients)
    n = len(patients)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    train = set(patients[:n_train])
    val = set(patients[n_train : n_train + n_val])
    test = set(patients[n_train + n_val :])

    def assign(pid: str) -> str:
        if pid in train:
            return "train"
        if pid in val:
            return "val"
        return "test"

    out["split"] = out["PatientID"].map(assign)
    return out
```

- [ ] **Step 3: Pytest PASS**

```bash
PYTHONPATH=. pytest tests/test_cohort.py -v
```

---

### Task 5: Registre colonnes — schéma + validation couverture

**Files:**
- Create: `src/data/registre.py`
- Create: `docs/registres/registre_colonnes.csv` (généré puis enrichi)
- Create: `tests/test_registre.py`
- Create: `scripts/generate_registre_skeleton.py`

**Interfaces:**
- Produces:
  - `REGISTRE_COLUMNS: list[str]` (schéma exact de la spec)
  - `load_registre(path: Path) -> pd.DataFrame`
  - `assert_registre_covers_sources(registre: pd.DataFrame, column_index: pd.DataFrame) -> None`
  - `assert_justifications(registre: pd.DataFrame) -> None`
  - `build_source_column_index(paths: ProjectPaths) -> pd.DataFrame` avec colonnes `fichier_source`, `colonne`

Schéma exact :

```text
fichier_source,colonne,grain,categorie,sensibilite,usage_score_sortie,usage_score_tele,justification_hopital,risque_principal,regle_nettoyage
```

- [ ] **Step 1: Script squelette** — lit les 11 CSV (headers seulement), écrit une ligne par colonne avec valeurs par défaut prudentes (`usage_* = exclu` pour identité ; `sante_art9` + `autorise` brouillon pour cliniques — **à finaliser dans notebook 03**).

Règles de préremplissage (figées) :

| Colonne | sensibilite | usage_sortie | usage_tele |
|---|---|---|---|
| NomPrenom, PersonneAPrevenir | identite_directe | exclu | exclu |
| MedecinTraitant | faible | exclu | exclu |
| Readmission30j | aucune | exclu | exclu |
| Colonnes objets_connectes (sauf clés) | capteur/sante | exclu | autorise (si Bon — règle nettoyage) |
| IndiceDefavorisation, DensiteMedicale, PopulationCommune | proxy_socio | autorise | autorise |
| Autres cliniques | sante_art9 | autorise | autorise |

Le script doit remplir `justification_hopital` non vide dès qu’`autorise` + sensibilité sensible (texte court type « Fragilité clinique / alerte sortie »).

- [ ] **Step 2: Tests couverture**

```python
from pathlib import Path
import pandas as pd
from src.data.paths import get_project_root, ProjectPaths
from src.data.registre import (
    build_source_column_index,
    load_registre,
    assert_registre_covers_sources,
    assert_justifications,
)


def test_registre_covers_all_columns():
    paths = ProjectPaths(root=get_project_root())
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    index = build_source_column_index(paths)
    assert_registre_covers_sources(registre, index)
    assert_justifications(registre)
```

- [ ] **Step 3: Implémenter `registre.py` + générer CSV + pytest PASS**

`assert_registre_covers_sources` lève `AssertionError` listant les colonnes manquantes/en trop.

`assert_justifications` :

```python
SENSITIVE = {"identite_directe", "sante_art9", "proxy_socio"}

def assert_justifications(registre: pd.DataFrame) -> None:
    mask = registre["usage_score_sortie"].eq("autorise") | registre["usage_score_tele"].eq("autorise")
    mask &= registre["sensibilite"].isin(SENSITIVE)
    bad = registre.loc[mask & registre["justification_hopital"].fillna("").str.strip().eq("")]
    if len(bad):
        raise AssertionError(f"Justifications manquantes:\n{bad[['fichier_source','colonne']]}")
```

```bash
PYTHONPATH=. python scripts/generate_registre_skeleton.py
PYTHONPATH=. pytest tests/test_registre.py -v
```

---

### Task 6: Features score sortie (anti-fuite temporelle)

**Files:**
- Create: `src/data/features_sortie.py`
- Create: `tests/test_features_sortie.py`

**Interfaces:**
- Consumes: sejours éligibles (Domicile + split), tables pseudonymisées, registre
- Produces: `build_features_score_sortie(...) -> pd.DataFrame`  
  Index grain = `SejourID`  
  Colonnes minimales obligatoires :
  - clés : `SejourID`, `PatientID`, `split`, `Readmission30j`
  - séjour : `DureeSejour`, `Service`, `TypeSejour`, `GHM`, `age_admission`, `Sexe`
  - historique pré-admission : `n_hosp_12m`, `n_urg_12m`, `n_consult_12m`
  - biologie : dernière valeur canonique non aberrante par panel **avant/à** DateSortie
  - constantes : moyenne des mesures in-range **≤ DateSortie** (FC, SpO2, Temp, …)
  - diagnostics : `n_diag`, `n_diag_principal`, flags top codes (ou count par Role)
  - actes : `n_actes` (DateActe ≤ DateSortie)
  - medications : `n_meds`, `n_voies`
  - territoire : `IndiceDefavorisation`, `DensiteMedicale`, `PopulationCommune` (jointure Commune+CodePostal)
  - **interdit** : toute colonne objets_connectes ; NomPrenom ; PersonneAPrevenir

- [ ] **Step 1: Test anti-fuite biologie post-sortie**

```python
import pandas as pd
from src.data.features_sortie import aggregate_biologie_pre_sortie


def test_biologie_ignore_post_sortie():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "DateSortie": ["2024-01-10 12:00:00"],
        }
    )
    bio = pd.DataFrame(
        {
            "SejourID": ["S1", "S1"],
            "DatePrelevement": ["2024-01-09 08:00:00", "2024-01-11 08:00:00"],
            "Panel": ["CRP", "CRP"],
            "Valeur_canonique": [10.0, 999.0],
            "flag_biologie_aberrante": [False, False],
        }
    )
    out = aggregate_biologie_pre_sortie(sejours, bio)
    assert out.loc[0, "bio_CRP_last"] == 10.0
```

- [ ] **Step 2: Implémenter agrégats + `build_features_score_sortie`**

Fonctions internes recommandées (toutes testables) :
- `compute_age_at_admission(patients, sejours) -> Series`
- `aggregate_historique_12m(sejours, historique) -> DataFrame`
- `aggregate_biologie_pre_sortie(sejours, biologies_harmonisees) -> DataFrame`
- `aggregate_signes_vitaux_pre_sortie(sejours, signes) -> DataFrame`
- `join_territoire(patients_pseudo, territoire) -> DataFrame` (sur PatientID via Commune/CP)

Assertions finales dans `build_features_score_sortie` :
```python
forbidden = {"NomPrenom", "PersonneAPrevenir"}
assert forbidden.isdisjoint(out.columns)
assert not any(c.startswith("oc_") for c in out.columns)
```

- [ ] **Step 3: Pytest PASS**

```bash
PYTHONPATH=. pytest tests/test_features_sortie.py -v
```

---

### Task 7: Features score télésurveillance (fenêtre fixe)

**Files:**
- Create: `src/data/features_tele.py`
- Create: `tests/test_features_tele.py`

**Interfaces:**
- Produces: `build_features_score_tele(features_sortie: pd.DataFrame, sejours: pd.DataFrame, objets_bons: pd.DataFrame, *, horizon_jours: int = 7) -> pd.DataFrame`
- Règle anti-fuite : fenêtre **identique** pour tous = `(DateSortie, DateSortie + horizon_jours]`  
  Ne **pas** tronquer à la date de réadmission (évite de coder le label dans la longueur de fenêtre). Documenter ce choix dans notebook 04.
- Agrégats : pour chaque `TypeMesure`, `oc_{type}_mean`, `oc_{type}_n`, `oc_coverage_days` (jours distincts avec ≥1 mesure Bon).

- [ ] **Step 1: Test fenêtre fixe**

```python
import pandas as pd
from src.data.features_tele import aggregate_objets_fenetre_fixe


def test_fenetre_fixe_7j():
    sejours = pd.DataFrame(
        {
            "SejourID": ["S1"],
            "PatientID": ["P1"],
            "DateSortie": ["2024-01-01 00:00:00"],
        }
    )
    oc = pd.DataFrame(
        {
            "PatientID": ["P1", "P1", "P1"],
            "Horodatage": [
                "2024-01-01 12:00:00",  # inclus (après sortie)
                "2024-01-05 12:00:00",  # inclus
                "2024-01-10 12:00:00",  # exclu (>7j)
            ],
            "TypeMesure": ["SpO2", "SpO2", "SpO2"],
            "Valeur": [95.0, 97.0, 80.0],
            "QualiteSignal": ["Bon", "Bon", "Bon"],
        }
    )
    out = aggregate_objets_fenetre_fixe(sejours, oc, horizon_jours=7)
    assert out.loc[0, "oc_SpO2_n"] == 2
    assert abs(out.loc[0, "oc_SpO2_mean"] - 96.0) < 1e-9
```

- [ ] **Step 2: Implémenter + concat features sortie + oc_***

- [ ] **Step 3: Pytest PASS**

```bash
PYTHONPATH=. pytest tests/test_features_tele.py -v
```

---

### Task 8: Orchestrateur CLI + exports curated

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `tests/test_pipeline_smoke.py`

**Interfaces:**
- `run_pipeline(paths: ProjectPaths, *, horizon_tele: int = 7) -> dict[str, Path]`  
  Écrit :
  - `data/pseudonymise/*.csv` (au minimum patients + copies des autres tables sans modification structurelle)
  - `data/curated/sejours_eligibles.parquet`
  - `data/curated/features_score_sortie.parquet`
  - `data/curated/features_score_tele.parquet`
  - `data/curated/rapport_export.json` (n, prévalence, listes de colonnes)

- [ ] **Step 1: Smoke test sur vrais CSV**

```python
from src.data.paths import ProjectPaths, get_project_root
from scripts.run_pipeline import run_pipeline  # ou src.pipeline


def test_pipeline_smoke(tmp_path):
    # Exécuter en écrivant curated dans un sous-dossier isolé si possible ;
    # sinon lancer sur le vrai root (données locales hors git).
    paths = ProjectPaths(root=get_project_root())
    out = run_pipeline(paths, horizon_tele=7)
    assert out["features_score_sortie"].exists()
    assert out["features_score_tele"].exists()
    import pandas as pd
    fs = pd.read_parquet(out["features_score_sortie"])
    assert "NomPrenom" not in fs.columns
    assert "Readmission30j" in fs.columns
    assert "split" in fs.columns
```

- [ ] **Step 2: Implémenter l’orchestrateur** (enchaîner Tasks 2–7 ; copier les CSV non-patients vers `pseudonymise/` tels quels).

- [ ] **Step 3: Exécuter**

```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/run_pipeline.py
PYTHONPATH=. pytest tests/test_pipeline_smoke.py -v
```

Expected: parquets créés ; smoke PASS.

---

### Task 9: Cinq notebooks narratifs

**Files:**
- Create: `notebooks/01_inventaire_sources.ipynb`
- Create: `notebooks/02_qualite_et_hallucinations.ipynb`
- Create: `notebooks/03_registre_sensibilite_rgpd.ipynb`
- Create: `notebooks/04_cohortes_deux_scores.ipynb`
- Create: `notebooks/05_export_features.ipynb`

Chaque notebook :
1. Markdown d’objectif + décisions (lien spec).
2. Cellules qui appellent `src.data.*` (pas de logique métier dupliquée).
3. Tableaux / counts pour le jury.
4. Cellule finale « critères d’acceptation » (asserts).

Contenu minimal par notebook :

| Notebook | Contenu |
|---|---|
| 01 | `build_source_column_index`, shapes, clés uniques, null rates |
| 02 | Appel `recalculate_duree_sejour`, counts flags physio/bio/capteurs, exemples **pseudonymisés** (PatientID seulement) |
| 03 | Afficher `registre_colonnes.csv`, filtres sensibilité, biais descriptifs âge/sexe/territoire sur cohorte Domicile |
| 04 | `filter_domicile`, `patient_level_split`, horizon télé=7 justifié (compter couverture objets connectés J+7 vs J+14) |
| 05 | `run_pipeline` ou lecture parquets + rapport ; assert registre ; assert no nominatif |

- [ ] **Step 1: Créer les 5 notebooks** (structure markdown + code exécutable).
- [ ] **Step 2: Exécuter séquentiellement** (kernel `.venv`) et corriger jusqu’à run all OK.
- [ ] **Step 3: Vérifier qu’aucun notebook n’importe de lib réseau / n’appelle d’URL.**

---

### Task 10: Documentation HTML chantier + checklist finale

**Files:**
- Create: `documentation/index.html`
- Create: `documentation/features/fondation-donnees.html`
- Create: `documentation/security/access-control.html`
- Create: `documentation/assets/styles.css`

Contenu FR, contrasté, navigation latérale simple : objectif, arborescence, registre, anti-fuite, hors-périmètre (ML/LLM à venir).

- [ ] **Step 1: Rédiger les pages** (pas de données patients).
- [ ] **Step 2: Suite pytest complète**

```bash
PYTHONPATH=. pytest -v
```

Expected: tous verts.

- [ ] **Step 3: Checklist acceptation spec §14** — cocher une par une dans le rapport notebook 05 / doc.

---

## Self-review (plan vs spec)

| Exigence spec | Task |
|---|---|
| 11 CSV only, local | Global + Task 2/8 |
| Coffre identité / pseudo | Task 2 |
| Qualité / hallucinations données | Task 3 + notebook 02 |
| Registre 100 % + justifications | Task 5 |
| Cohorte Domicile | Task 4 |
| Split patient | Task 4 |
| Score sortie cutoff | Task 6 |
| Score télé fenêtre fixe + Bon | Task 7 |
| Exports curated | Task 8 |
| Notebooks 01–05 | Task 9 |
| Tests anti-fuite | Tasks 3–7 |
| gitignore données | Task 1 |
| Doc HTML | Task 10 |
| LLM / ML | Explicitement hors plan (roadmap spec §3) |

Pas de TBD restants. Signatures alignées entre tasks (`ProjectPaths`, `recalculate_duree_sejour`, `build_features_score_*`).

---

## Hors plan (prochains specs)

- Modèle tabulaire (LightGBM / baseline) + biais + SHAP local.
- LLM local (GGUF + LoRA sur CR masqués) + métriques hallucination / fuite identité.
- Webapp démo locale.
- Livrables CIF C1–C3 / C7–C8.
