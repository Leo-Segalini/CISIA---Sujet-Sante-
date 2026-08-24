# Spec — Fondation données : réadmission hospitalière 30 jours

- **Date :** 2026-08-24
- **Statut :** validée en conception (sections 1–3), en attente de relecture fichier
- **Périmètre :** sous-projet 1 uniquement (audit, registre, cohortes, exports de features)
- **Projet parent :** CISIA Santé — prédiction du risque de réadmission à 30 jours

## 1. Contexte et objectif

Le groupement hospitalier (simulation pédagogique) doit distinguer les sorties à faible risque des sorties nécessitant un suivi renforcé, à partir des **11 CSV fournis uniquement**. Les données sont **synthétiques** ; elles ne doivent jamais servir à une décision clinique réelle.

Ce sous-projet ne entraîne **aucun** modèle tabulaire ni LLM. Il produit la base **traçable, locale et sécurisée** sans laquelle les modèles suivants ne peuvent pas être justifiés.

**Livrable de succès :** un jury peut ouvrir le registre et les cinq notebooks et voir, pour **chaque colonne** des CSV, la sensibilité, l’usage par score, la justification hospitalière, et la règle de nettoyage — sans nominatif dans `data/curated/`.

## 2. Décisions figées

| Décision | Choix |
|---|---|
| Premier chantier | Fondation données + notebooks d’audit |
| Scores | **Deux scores distincts** : sortie (SIH) et télésurveillance post-sortie |
| Cohorte ML | **`ModeSortie = Domicile` uniquement** ; Décès, Transfert, EHPAD, HAD = audit descriptif hors entraînement |
| Identité | **Double jeu** : coffre identité vs jeu pseudonymisé |
| Sources | **Uniquement les 11 CSV** ; aucun enrichissement externe |
| Colonnes sensibles | Toutes cataloguées ; une variable sensible **peut** entrer dans l’IA si étiquetée **et** justifiée (bénéfice hôpital) ; le nominatif reste hors scores |
| Architecture audit | Pipeline **modulaire** + `registre_colonnes.csv` machine-lisible |
| Exécution | 100 % local ; aucun modèle ni API en ligne ; aucune donnée de santé hors machine |

## 3. Roadmap des sous-projets (hors implémentation ici)

L’entraînement d’un **LLM local performant** est **exigé** pour le projet global, pas pour ce chantier.

1. **Fondation données** (cette spec) — registre, qualité, deux jeux de features.
2. **Modèle tabulaire** — prédiction `Readmission30j` (score sortie puis score télé), biais, explicabilité, tout local.
3. **LLM local performant** — modèles **téléchargés puis exécutés hors ligne** (GGUF / Transformers local). Usages visés : lecture des comptes-rendus, extraction structurée, justification en langage clair du score, garde-fous (pas de nominatif, pas d’invention clinique). Entraînement / adaptation locale (LoRA ou équivalent) **sur texte pseudonymisé uniquement**, avec métriques (fidélité au CR, absence d’hallucination, fuite d’identité). Détail dans une spec dédiée après la fondation.
4. **Webapp de démo locale** — scores + registre + piste d’audit.
5. **Livrables CIF** — C1, C2, C3, C7, C8 ancrés sur ce poste et cette arborescence.

Le LLM **n’utilise pas** le coffre identité. Les CR passent par un masquage des identifiants avant toute adaptation.

## 4. Architecture et flux

```text
data/
  raw/                      # copies locales des 11 CSV (nominatif présent) — hors git
  vault_identite/           # table d’appariement PatientID ↔ nominatif/contacts — hors git
  pseudonymise/             # tables sans NomPrenom, PersonneAPrevenir
  curated/
    sejours_eligibles.parquet
    features_score_sortie.parquet
    features_score_tele.parquet
docs/
  registres/
    registre_colonnes.csv
notebooks/
  01_inventaire_sources.ipynb
  02_qualite_et_hallucinations.ipynb
  03_registre_sensibilite_rgpd.ipynb
  04_cohortes_deux_scores.ipynb
  05_export_features.ipynb
src/data/                   # chargement, nettoyage, jointures, cutoff, split patient
tests/                      # tests unitaires des règles ci-dessous
```

**Flux :** CSV bruts → inventaire → séparation vault / pseudonyme → contrôles qualité → registre sensibilité → cohorte Domicile + split patient → features score sortie (cutoff `DateSortie`) → features score télé (fenêtre post-sortie sans fuite de label) → exports `curated/` + rapport.

Les CSV d’origine restent à la racine du dépôt pédagogique fourni ; le pipeline **copie** vers `data/raw/` sans modifier les fichiers sources du sujet.

## 5. Définition des deux scores (contrats)

### 5.1 Score sortie (opérationnel SIH)

- **Moment :** à la sortie du séjour index.
- **Unité :** un séjour (`SejourID`) d’un patient en sortie `Domicile`.
- **Cible :** `Readmission30j` telle que fournie (contrôlée en cohérence, jamais recalculée comme feature).
- **Features autorisées :** toute colonne du registre avec `usage_score_sortie = autorise`, horodatage ≤ `DateSortie`.
- **Interdit :** nominatif ; mesures `objets_connectes` ; toute info postérieure à la sortie.

### 5.2 Score télésurveillance

- **Moment :** après la sortie (fenêtre documentée dans le notebook 04, par défaut agrégats sur J+0 à J+7, avec variante J+14 si le volume le permet — un seul horizon **principal** figé dans le notebook 04 après comptage, l’autre en analyse de sensibilité).
- **Unité :** même séjour index, sortie `Domicile`.
- **Cible :** la même `Readmission30j`.
- **Features :** features du score sortie **disponibles à la sortie** + agrégats objets connectés après `DateSortie` et **strictement avant** la date de réadmission si `Readmission30j = 1` (si la date de réadmission n’est pas dans les CSV, utiliser uniquement une fenêtre calendaire fixe post-sortie identique pour tous, pour ne pas coder le label dans la longueur de fenêtre).
- **Qualité capteur :** agrégation ML seulement si `QualiteSignal = Bon`.

## 6. Notebooks

### 01 — Inventaire

Grain, clés, cardinalités, types, jointures. Aucun nettoyage. Sortie : tableau source → grain → clés.

### 02 — Qualité et « hallucinations »

Hallucination **données** = valeur ou relation **impossible ou contradictoire** (durée négative, constante non physiologique, unité biologie incohérente, capteur défaillant, acte/diagnostic orphelin, CR vide ou contradictoire avec le GHM, label incompatible avec un décès, etc.).

Pour chaque règle : fréquence, exemple **pseudonymisé**, action (`corriger` / `flag` / `censurer` / `exclure la ligne`).

### 03 — Registre sensibilité / RGPD

Remplit `docs/registres/registre_colonnes.csv`. Sépare coffre et jeu de travail. Biais descriptifs : âge, sexe, territoire, intensité d’usage des soins.

### 04 — Cohortes et deux scores

Unité = séjour index. Filtre Domicile. Split **par `PatientID`**. Documente les cutoffs et l’horizon télé retenu.

### 05 — Export features

Écrit les parquets curated et un rapport (n, prévalence, liste des features liées au registre). **Pas d’entraînement.**

## 7. Schéma du registre

Colonnes obligatoires de `registre_colonnes.csv` :

- `fichier_source`
- `colonne`
- `grain` : `patient` | `sejour` | `evenement` | `commune`
- `categorie` : `identite` | `clinique` | `parcours` | `texte` | `capteur` | `territoire` | `cible`
- `sensibilite` : `identite_directe` | `sante_art9` | `proxy_socio` | `faible` | `aucune`
- `usage_score_sortie` : `exclu` | `flag_only` | `autorise`
- `usage_score_tele` : `exclu` | `flag_only` | `autorise`
- `justification_hopital` : texte ; **obligatoire** si `autorise` et `sensibilite` ∈ {`identite_directe`, `sante_art9`, `proxy_socio`}
- `risque_principal` : `fuite` | `biais` | `qualite` | `secret_medical` | `none`
- `regle_nettoyage` : courte et reproductible

**Couverture :** 100 % des colonnes présentes dans les 11 CSV. Toute colonne absente du registre fait **échouer** le notebook 05.

Règles d’intention (à confirmer dans le notebook 03, pas à inventer hors données) :

- `NomPrenom`, `PersonneAPrevenir` → coffre, `exclu` des deux scores.
- `MedecinTraitant` → identifiant professionnel ; `exclu` des scores (réidentification / biais établissement), conservé en audit.
- Biologie, constantes, CIM-10, CCAM, ATC, GHM, pathologies, textes CR (après masquage) → `sante_art9` ; `autorise` si justification renseignée.
- `RegimeAssurance`, `SituationFamiliale` → sensibles / proxy ; `autorise` **seulement** avec justification hôpital et analyse de biais, sinon `flag_only`.
- `IndiceDefavorisation`, `DensiteMedicale`, `PopulationCommune` → `proxy_socio` territorial agrégé (autorisé par le sujet comme proxy, pas comme donnée socio-éco individuelle) ; `autorise` avec justification organisation territoriale + analyse de biais.
- Mesures objets connectés → `exclu` score sortie ; score télé selon qualité.

## 8. Règles de qualité

- Recalculer `DureeSejour` depuis `DateAdmission` / `DateSortie` si incohérence (négatif ou écart > 1 jour). Conserver `DureeSejour_brute` + flag.
- Biologie : harmonisation **par `Panel`** vers une unité canonique ; hors référence ou hors plage → flag, **pas d’imputation silencieuse**.
- Constantes : plages physiologiques **écrites dans le code** (une table unique) ; hors plage → exclu de l’agrégat, ligne séjour conservée.
- Objets connectés : features ML uniquement `QualiteSignal = Bon`.
- Comptes-rendus : aucun appel réseau ; métriques locales (longueur, vide, détection de motifs nominatifs à masquer). Pas d’annotation manuelle massive.

## 9. Anti-fuite (bloquant)

- Split **patient-level** (train / validation / test).
- Score sortie : aucune feature horodatée **après** `DateSortie`.
- Score télé : pas de mesure à la date de réadmission ou après ; pas de variable dérivée du label ; pas de fenêtre plus longue pour les réadmis que pour les non-réadmis.
- `Readmission30j` n’est jamais une feature.
- Décès hors ML ; si `Readmission30j = 1` malgré un décès, consigner en anomalie d’audit.

## 10. Erreurs et tests

**Erreurs :** CSV illisible ou clé absente → arrêt avec fichier / colonne / n. Jointure territoire sans match → `territoire_inconnu`, pas de suppression silencieuse. Registre incomplet → échec notebook 05.

**Tests unitaires locaux :** recalcul de durée ; respect des cutoffs ; absence de colonnes nominatives dans `curated/` ; unicité des clés ; filtre Domicile ; couverture 100 % du registre. Pas de test d’accuracy de modèle dans ce sous-projet.

## 11. Sécurité et git

- `.gitignore` : `data/raw/`, `data/vault_identite/`, `data/pseudonymise/`, `data/curated/`, artefacts notebooks avec extraits bruts si besoin.
- Versionnés : notebooks, `src/`, `tests/`, `docs/registres/registre_colonnes.csv` (métadonnées **sans** lignes patients), ce document.
- Les 11 CSV du sujet restent le jeu pédagogique d’entrée ; ils contiennent du nominatif synthétique : **ne pas les pousser** vers un dépôt distant public. Travail 100 % local.

## 12. Hors périmètre de cette spec

- Entraînement LightGBM / régression / réseau tabulaire.
- Téléchargement, adaptation et évaluation du **LLM local** (spec suivante).
- Webapp de démo.
- Rédaction finale du livret CIF, du support visuel C3 et du compte-rendu C7/C8 (l’arborescence de cette spec **alimente** C7/C8).

## 13. Stack de ce chantier

- Python 3.11+, Jupyter, pandas, pyarrow.
- Tests : pytest.
- Pas de service cloud. Pas de nouvelle dépendance lourde (pas de Great Expectations complet) ; asserts ciblés dans `src/` et pytest.

## 14. Critères d’acceptation

1. Cinq notebooks exécutables hors ligne à partir des CSV locaux.
2. `registre_colonnes.csv` couvre toutes les colonnes sources, sans case vide sur `usage_score_*` ni `sensibilite`.
3. `justification_hopital` non vide pour tout champ `autorise` sensible.
4. `features_score_sortie.parquet` sans colonnes nominatives ni objets connectés.
5. `features_score_tele.parquet` sans nominatif ; objets connectés uniquement `Bon` et post-sortie.
6. Tests pytest verts sur les règles d’anti-fuite et de durée.
7. Aucun appel réseau dans le code de ce chantier.
