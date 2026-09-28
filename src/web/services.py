from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache

import joblib
import pandas as pd

from src.data.identity import split_identity_and_pseudonymise
from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root
from src.data.registre import load_registre
from src.data.territoire import load_territoire_enrichi, write_complements
from src.data.vitals import (
    enrich_signes_vitaux,
    historique_constantes_sejour,
    index_dernieres_mesures,
    signes_valides,
)
from src.model.prepare import ID_COLS, SPLIT_COL, TARGET_COL, split_xy
from src.model.explain_patient import build_explication_risque_30j, facteurs_risque_patient
from src.model.inference import score_single
from src.nlp.guardrails import grounded_justification
from src.nlp.local_llm import (
    generate_brief_text,
    generate_justification,
    resolve_gguf,
)
from src.nlp.llm_process import get_llm_bridge, llm_obligatoire
from src.nlp.masking import documents_par_sejour, mask_comptes_rendus
from src.web.affichage import (
    format_feature_value,
    libelle_feature,
    libelle_sexe,
    nom_famille,
    pathologies_libelle,
    prenom,
)
from src.web.live import (
    EQUIPE_PAR_SERVICE,
    equipe_complete,
    libelle_personne,
    EPOCH_TICKS,
    FLOOR_PLAN,
    MAX_LITS_PAR_SERVICE,
    MAX_URGENT_PAR_SERVICE,
    MEDECIN_PAR_ETAGE,
    MONITEUR_REFRESH_SEC,
    SERVICE_DATA_SOURCE,
    SERVICE_LABELS,
    TICK_SECONDS,
    UNITE_PAR_SERVICE,
    alertes_machines,
    appliquer_urgence_pedagogique,
    appliquer_vitals_urgence_pedagogique,
    current_tick,
    fenetre_urgence_pedagogique,
    index_constantes,
    libelle_mode_monitoring,
    localisation_pour,
    message_soignant,
    score_news_simplifie,
    sejour_est_urgence_pedagogique,
    sejours_pour_service,
    series_evolution_from_historique,
    series_evolution_live,
    service_est_monitoring_continu,
    slots_lits_service,
    snapshot_constantes,
    statut_constantes_alerte,
    tendance_constantes,
)


@dataclass
class DemoStore:
    paths: ProjectPaths
    features: pd.DataFrame
    metrics: dict
    bundle: dict
    docs: pd.DataFrame
    registre: pd.DataFrame
    shap: pd.DataFrame
    vitals_by_sej: dict
    dernieres_vitals_by_sej: dict
    signes_view: pd.DataFrame
    patients_view: pd.DataFrame
    sejours_view: pd.DataFrame
    territoire: pd.DataFrame
    score_cache: dict = field(default_factory=dict)
    llm_cache: dict = field(default_factory=dict)
    _llm_bridge: object | None = None
    _llm_tried: bool = False
    _llm_jobs: set = field(default_factory=set)
    # Démo lit : (service_code, chambre, lit)
    lits_nettoyes: set = field(default_factory=set)
    admissions_demo: dict = field(default_factory=dict)
    deces_assignes: dict = field(default_factory=dict)  # clé lit → SejourID décès
    # Saisies infirmières manuelles : SejourID → liste chronologique de mesures
    constantes_manueles: dict = field(default_factory=dict)
    _deces_init: bool = False

    def try_start_llm(self) -> None:
        if self._llm_tried:
            return
        self._llm_tried = True
        if not llm_obligatoire():
            self._llm_bridge = None
            return
        try:
            path = resolve_gguf(self.paths.models)
            if path is None:
                self._llm_bridge = None
                return
            self._llm_modele = path.name
            self._llm_bridge = get_llm_bridge(path)
        except Exception:
            self._llm_bridge = None

    @property
    def llm(self):
        """Bridge LLM (truthy si disponible)."""
        b = self._llm_bridge
        if b is not None and getattr(b, "disponible", False):
            return b
        return None

    @property
    def llm_modele(self) -> str | None:
        return getattr(self, "_llm_modele", None)

    @property
    def llm_statut(self) -> str:
        if not llm_obligatoire():
            return "désactivé (CISIA_LLM=0)"
        if self._llm_bridge is None:
            modele = self.llm_modele
            if modele:
                return f"non démarré ({modele})"
            return "non démarré (aucun GGUF — scripts/download_gguf.py)"
        base = getattr(self._llm_bridge, "statut", "inconnu")
        if self.llm_modele:
            return f"{base} · {self.llm_modele}"
        return base

    def enqueue_brief(self, cache_key: str, chambre: str, vitals: dict, document: str) -> None:
        """Génère le brief IA en arrière-plan (ne bloque pas /api/live)."""
        if cache_key in self.llm_cache or cache_key in self._llm_jobs:
            return
        if self.llm is None:
            return
        self._llm_jobs.add(cache_key)

        def _run() -> None:
            try:
                text = generate_brief_text(self.llm, chambre, vitals, document)
                self.llm_cache[cache_key] = text or ""
            except Exception:
                self.llm_cache[cache_key] = ""
            finally:
                self._llm_jobs.discard(cache_key)

        threading.Thread(target=_run, daemon=True).start()


def _patients_affichage(patients: pd.DataFrame, vault: pd.DataFrame) -> pd.DataFrame:
    """Nom de famille + prénom (liste lits) + sexe ; contact reste hors UI."""
    base = patients.drop(columns=["NomPrenom", "PersonneAPrevenir"], errors="ignore").copy()
    names = vault[["PatientID", "NomPrenom"]].copy()
    names["NomFamille"] = names["NomPrenom"].map(nom_famille)
    names["Prenom"] = names["NomPrenom"].map(prenom)
    names = names.drop(columns=["NomPrenom"])
    out = base.merge(names, on="PatientID", how="left")
    out["SexeLibelle"] = out["Sexe"].map(libelle_sexe)
    out["Antecedents"] = out.get(
        "PathologiesChroniques", pd.Series(index=out.index)
    ).map(pathologies_libelle)
    return out


def _load_store() -> DemoStore:
    paths = ProjectPaths(root=get_project_root())
    parquet = paths.curated / "features_score_sortie.parquet"
    if not parquet.exists():
        raise FileNotFoundError(
            "features_score_sortie.parquet manquant — lancer scripts/run_pipeline.py"
        )
    metrics_path = paths.models / "score_sortie_metrics.json"
    bundle_path = paths.models / "score_sortie_bundle.joblib"
    if not metrics_path.exists() or not bundle_path.exists():
        raise FileNotFoundError(
            "Modèles absents — lancer scripts/train_models.py"
        )
    features = pd.read_parquet(parquet)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    bundle = joblib.load(bundle_path)
    shap_path = paths.models / "score_sortie_shap.csv"
    shap = (
        pd.read_csv(shap_path)
        if shap_path.exists()
        else pd.DataFrame(columns=["feature", "mean_abs_shap"])
    )
    patients = load_csv(paths, "patients.csv", from_raw=False)
    vault, _ = split_identity_and_pseudonymise(patients)
    sejours = load_csv(paths, "sejours.csv", from_raw=False)
    cr = load_csv(paths, "comptes_rendus.csv", from_raw=False)
    docs = documents_par_sejour(mask_comptes_rendus(cr, vault, sejours))
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    signes_raw = load_csv(paths, "signes_vitaux.csv", from_raw=False)
    signes_view = enrich_signes_vitaux(signes_raw)
    territoire_sujet = load_csv(paths, "territoire_insee.csv", from_raw=False)
    write_complements(paths, territoire_sujet)
    territoire = load_territoire_enrichi(paths, territoire_sujet)
    return DemoStore(
        paths=paths,
        features=features,
        metrics=metrics,
        bundle=bundle,
        docs=docs,
        registre=registre,
        shap=shap,
        vitals_by_sej=index_constantes(signes_valides(signes_raw)),
        dernieres_vitals_by_sej=index_dernieres_mesures(signes_view),
        signes_view=signes_view,
        patients_view=_patients_affichage(patients, vault),
        sejours_view=sejours.copy(),
        territoire=territoire,
    )


@lru_cache(maxsize=1)
def get_store() -> DemoStore:
    return _load_store()


def _patient_card(store: DemoStore, patient_id: str) -> dict:
    row = store.patients_view.loc[store.patients_view["PatientID"] == patient_id]
    if row.empty:
        return {
            "NomFamille": "—",
            "Prenom": "—",
            "Sexe": "—",
            "SexeLibelle": "Non renseigné",
            "Antecedents": "Aucun antécédent renseigné",
            "Commune": "—",
            "CodePostal": "—",
            "RegimeAssurance": "—",
        }
    r = row.iloc[0]
    return {
        "NomFamille": str(r.get("NomFamille", "—")),
        "Prenom": str(r.get("Prenom", "—")),
        "Sexe": str(r.get("Sexe", "—")),
        "SexeLibelle": str(r.get("SexeLibelle", "Non renseigné")),
        "Antecedents": str(r.get("Antecedents", "Aucun antécédent renseigné")),
        "Commune": str(r.get("Commune", "—")),
        "CodePostal": str(r.get("CodePostal", "—")),
        "RegimeAssurance": str(r.get("RegimeAssurance", "—")),
    }


def _territoire_card(store: DemoStore, commune: str, code_postal: str) -> dict:
    terr = store.territoire
    hit = terr.loc[
        (terr["Commune"].astype(str) == str(commune))
        & (terr["CodePostal"].astype(str) == str(code_postal))
    ]
    if hit.empty:
        return {}
    r = hit.iloc[0]

    def _num(col: str):
        v = r.get(col)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "IndiceDefavorisation": _num("IndiceDefavorisation"),
        "DensiteMedicale": _num("DensiteMedicale"),
        "PopulationCommune_sujet": _num("PopulationCommune"),
        "INSEE_ajoute_CodeCommune": None
        if pd.isna(r.get("INSEE_ajoute_CodeCommune"))
        else str(r.get("INSEE_ajoute_CodeCommune")),
        "INSEE_ajoute_PopulationLegale": _num("INSEE_ajoute_PopulationLegale"),
        "INSEE_ajoute_PartPlus65Ans_pct": _num("INSEE_ajoute_PartPlus65Ans_pct"),
        "INSEE_ajoute_Departement": None
        if pd.isna(r.get("INSEE_ajoute_Departement"))
        else str(r.get("INSEE_ajoute_Departement")),
        "INSEE_ajoute_Region": None
        if pd.isna(r.get("INSEE_ajoute_Region"))
        else str(r.get("INSEE_ajoute_Region")),
        "INSEE_ajoute_EcartPop_vs_sujet": _num("INSEE_ajoute_EcartPop_vs_sujet"),
        "INSEE_ajoute_Millesime": None
        if pd.isna(r.get("INSEE_ajoute_Millesime"))
        else str(r.get("INSEE_ajoute_Millesime")),
    }


def _sejour_admin(store: DemoStore, sejour_id: str) -> dict:
    row = store.sejours_view.loc[store.sejours_view["SejourID"] == sejour_id]
    if row.empty:
        return {}
    r = row.iloc[0]
    return {
        "DateAdmission": str(r.get("DateAdmission", "")),
        "DateSortie": str(r.get("DateSortie", "")),
        "DureeSejour": None if pd.isna(r.get("DureeSejour")) else int(r.get("DureeSejour")),
        "TypeSejour": str(r.get("TypeSejour", "")),
        "GHM": str(r.get("GHM", "")),
        "ModeSortie": str(r.get("ModeSortie", "")),
    }


def _score_row(store: DemoStore, sejour_id: str) -> dict:
    if sejour_id in store.score_cache:
        return store.score_cache[sejour_id]
    row = store.features.loc[store.features["SejourID"] == sejour_id]
    X, y, split = split_xy(row)
    scored = score_single(store.bundle, store.metrics, X)
    out = {
        "proba": scored["proba"],
        "seuil": scored["seuil"],
        "alerte": scored["alerte"],
        "modele": scored["modele"],
        "label": int(y.iloc[0]),
        "split": str(split.iloc[0]),
        "patient": str(row["PatientID"].iloc[0]),
        "service": str(row["Service"].iloc[0]),
        "age": row["age_admission"].iloc[0],
        "n_meds": row["n_meds"].iloc[0] if "n_meds" in row.columns else None,
        "n_diag": row["n_diag"].iloc[0] if "n_diag" in row.columns else None,
    }
    store.score_cache[sejour_id] = out
    return out


def reload_store() -> None:
    """Recharge modèles et données après ré-entraînement."""
    get_store.cache_clear()


def lits_filter_options() -> dict:
    """Options pour les filtres de la page « Tous les lits »."""
    return {
        "etages": [
            {"value": str(f["etage"]), "label": f["etage_libelle"]} for f in FLOOR_PLAN
        ],
        "services": [
            {"value": code, "label": label} for code, label in SERVICE_LABELS.items()
        ],
        "sexes": [
            {"value": "M", "label": "Homme"},
            {"value": "F", "label": "Femme"},
        ],
    }


def list_sejours(
    *,
    q: str = "",
    etage: int | None = None,
    service: str = "",
    sexe: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    store = get_store()
    rows = []
    for sej in store.features["SejourID"].tolist():
        sc = _score_row(store, sej)
        loc = localisation_pour(sej, sc["service"])
        pat = _patient_card(store, sc["patient"])
        rows.append(
            {
                "SejourID": sej,
                "PatientID": sc["patient"],
                "NomFamille": pat["NomFamille"],
                "Prenom": pat["Prenom"],
                "Sexe": pat["Sexe"],
                "SexeLibelle": pat["SexeLibelle"],
                "Service": sc["service"],
                "service_libelle": SERVICE_LABELS.get(sc["service"], sc["service"]),
                "age_admission": sc["age"],
                "etage": loc["etage"],
                "chambre": loc["chambre"],
                "lit": loc["lit"],
                "lit_complet": loc["lit_complet"],
                "aile": loc["aile"],
                "etage_libelle": loc["etage_libelle"],
                "poste": loc["poste"],
                TARGET_COL: int(
                    store.features.loc[
                        store.features["SejourID"] == sej, TARGET_COL
                    ].iloc[0]
                ),
                "split": sc["split"],
            }
        )
    df = pd.DataFrame(rows)
    if q.strip():
        qq = q.strip().upper()
        df = df.loc[
            df["SejourID"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["PatientID"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["NomFamille"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["Prenom"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["chambre"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["lit_complet"].astype(str).str.upper().str.contains(qq, regex=False)
        ]
    if etage is not None:
        df = df.loc[df["etage"] == etage]
    if service.strip():
        df = df.loc[df["Service"] == service.strip()]
    if sexe.strip():
        df = df.loc[df["Sexe"].astype(str).str.upper() == sexe.strip().upper()]
    df = df.sort_values(["etage", "chambre", "lit", "SejourID"])
    total = int(len(df))
    page = max(1, page)
    start = (page - 1) * page_size
    chunk = df.iloc[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": chunk.to_dict(orient="records"),
        "filters": {
            "q": q.strip(),
            "etage": etage,
            "service": service.strip(),
            "sexe": sexe.strip().upper() if sexe.strip() else "",
        },
    }


def _medicaments_sejour(store: DemoStore, sejour_id: str) -> list[dict[str, Any]]:
    """Prescriptions du séjour (libellé, ATC, posologie, voie, dates)."""
    if not hasattr(store, "_meds_df") or store._meds_df is None:
        try:
            store._meds_df = load_csv(store.paths, "medications.csv", from_raw=False)
        except Exception:  # noqa: BLE001
            store._meds_df = pd.DataFrame()
    meds = store._meds_df
    if meds is None or meds.empty or "SejourID" not in meds.columns:
        return []
    sub = meds.loc[meds["SejourID"].astype(str) == str(sejour_id)].copy()
    if sub.empty:
        return []
    if "DateDebut" in sub.columns:
        sub = sub.sort_values("DateDebut", na_position="last")
    out: list[dict[str, Any]] = []
    for _, row in sub.iterrows():
        out.append(
            {
                "CodeATC": str(row.get("CodeATC") or "—"),
                "Libelle": str(row.get("LibelleMedicament") or "—"),
                "Posologie": str(row.get("Posologie") or "—"),
                "Voie": str(row.get("Voie") or "—"),
                "DateDebut": str(row.get("DateDebut") or "—")[:10],
                "DateFin": (
                    str(row.get("DateFin") or "—")[:10]
                    if pd.notna(row.get("DateFin")) and str(row.get("DateFin")).strip()
                    else "en cours"
                ),
            }
        )
    return out


def _poids_patient(store: DemoStore, patient_id: str) -> float | None:
    """Dernier poids objets connectés (signal Bon), s’il existe."""
    if not hasattr(store, "_objets_df") or store._objets_df is None:
        try:
            store._objets_df = load_csv(store.paths, "objets_connectes.csv", from_raw=False)
        except Exception:  # noqa: BLE001
            store._objets_df = pd.DataFrame()
    oc = store._objets_df
    if oc is None or oc.empty:
        return None
    mask = (
        (oc["PatientID"].astype(str) == str(patient_id))
        & (oc["TypeMesure"].astype(str) == "Poids")
        & (oc["QualiteSignal"].astype(str) == "Bon")
    )
    sub = oc.loc[mask]
    if sub.empty:
        return None
    if "Horodatage" in sub.columns:
        sub = sub.sort_values("Horodatage")
    try:
        return round(float(sub.iloc[-1]["Valeur"]), 1)
    except (TypeError, ValueError):
        return None


_VITAL_KEYS_SAISIE = (
    "FrequenceCardiaque",
    "SpO2",
    "TensionSystolique",
    "TensionDiastolique",
    "Temperature",
    "FrequenceRespiratoire",
    "PoidsKg",
)


def _constantes_depuis_historique(
    store: DemoStore, sejour_id: str
) -> dict[str, Any]:
    """Dernière mesure retenue du dossier (CSV), ou vide."""
    hist = historique_constantes_sejour(store.signes_view, sejour_id)
    retenues = hist.get("mesures_retenues") or []
    if not retenues:
        return {}
    # mesures_retenues : plus récent en premier
    last = retenues[0]
    out: dict[str, Any] = {}
    for k in _VITAL_KEYS_SAISIE:
        v = last.get(k)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            out[k] = float(v)
    return out


def _historique_enrichi_saisies(
    store: DemoStore, sejour_id: str
) -> dict[str, Any]:
    """Historique dossier + saisies infirmières (pour graphiques / tableau)."""
    hist = historique_constantes_sejour(store.signes_view, sejour_id)
    saisies = list(store.constantes_manueles.get(str(sejour_id), []))
    if not saisies:
        return hist
    extras = []
    for i, s in enumerate(saisies):
        extras.append(
            {
                "ConstanteID": s.get("ConstanteID") or f"SAISIE-{i + 1}",
                "Horodatage": s.get("Horodatage"),
                "FrequenceCardiaque": s.get("FrequenceCardiaque"),
                "TensionSystolique": s.get("TensionSystolique"),
                "TensionDiastolique": s.get("TensionDiastolique"),
                "Temperature": s.get("Temperature"),
                "FrequenceRespiratoire": s.get("FrequenceRespiratoire"),
                "SpO2": s.get("SpO2"),
                "PoidsKg": s.get("PoidsKg"),
                "exclue": False,
                "motif_exclusion": None,
                "source": "saisie_infirmiere",
            }
        )
    # Fusion : plus récent d’abord
    mesures = extras[::-1] + list(hist.get("mesures") or [])
    retenues = [m for m in mesures if not m.get("exclue")]
    exclues = [m for m in mesures if m.get("exclue")]
    return {
        **hist,
        "total": len(mesures),
        "retenues": len(retenues),
        "exclues": len(exclues),
        "mesures": mesures,
        "mesures_retenues": retenues,
        "mesures_exclues": exclues,
    }


def _vitals_manuel_courants(store: DemoStore, sejour_id: str) -> dict[str, Any]:
    """Dernière saisie infirmière, sinon dernière mesure dossier (index O(1))."""
    saisies = store.constantes_manueles.get(str(sejour_id)) or []
    if saisies:
        last = saisies[-1]
        return {k: last.get(k) for k in _VITAL_KEYS_SAISIE if last.get(k) is not None}
    cached = store.dernieres_vitals_by_sej.get(str(sejour_id))
    if cached:
        return dict(cached)
    return _constantes_depuis_historique(store, sejour_id)


def _vitals_live_pour_sejour(store: DemoStore, sejour_id: str, service: str) -> dict[str, Any]:
    """Constantes selon le mode du service (live machines vs saisie manuelle)."""
    loc = localisation_pour(sejour_id, service)
    continu = service_est_monitoring_continu(service)
    tick = current_tick()
    profil = store.vitals_by_sej.get(sejour_id)

    if continu:
        vitals = snapshot_constantes(profil, tick=tick)
        etage_lib = str(loc["etage_libelle"])
        candidats_ids: list[str] = []
        floor = next((f for f in FLOOR_PLAN if f["etage_libelle"] == etage_lib), None)
        if floor:
            for svc in floor["services"]:
                if not service_est_monitoring_continu(svc):
                    continue
                for room in _rooms_for_service(
                    store, svc, tick, max_par_service=MAX_LITS_PAR_SERVICE
                ):
                    if (
                        room.get("SejourID")
                        and not room.get("vide")
                        and room.get("niveau") not in {"disponible", "a_nettoyer"}
                    ):
                        candidats_ids.append(str(room["SejourID"]))
        urgence_demo, urgence_restant_s = sejour_est_urgence_pedagogique(
            sejour_id, candidats_ids, etage_libelle=etage_lib
        )
        if urgence_demo:
            vitals = appliquer_vitals_urgence_pedagogique(vitals)
        charts = series_evolution_live(
            profil,
            tick=tick,
            vitals_override=vitals if urgence_demo else None,
        )
        tendance = tendance_constantes(profil, tick=tick)
        refresh = MONITEUR_REFRESH_SEC
    else:
        vitals = _vitals_manuel_courants(store, sejour_id)
        urgence_demo, urgence_restant_s = False, 0
        hist = _historique_enrichi_saisies(store, sejour_id)
        charts = series_evolution_from_historique(hist)
        tendance = "stable"
        refresh = 0

    machines = alertes_machines(vitals) if vitals else []
    return {
        "SejourID": sejour_id,
        "tick": tick,
        "monitoring_continu": continu,
        "mode_monitoring": libelle_mode_monitoring(service),
        "service_code": service,
        "refresh_seconds": refresh,
        "tick_seconds": TICK_SECONDS,
        "epoch_seconds": EPOCH_TICKS * TICK_SECONDS,
        "constantes": vitals,
        "constantes_alerte": statut_constantes_alerte(vitals) if vitals else {},
        "score_news": score_news_simplifie(vitals) if vitals else None,
        "alertes_machines": machines,
        "urgence_pedagogique": urgence_demo,
        "urgence_restant_s": urgence_restant_s,
        "tendance_constantes": tendance,
        "series": charts,
        "n_saisies_manuel": len(store.constantes_manueles.get(str(sejour_id), [])),
    }


def saisir_constantes_sejour(sejour_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Enregistre une saisie infirmière (services hors monitoring continu)."""
    store = get_store()
    scored = _score_row(store, sejour_id)
    service = scored["service"]
    if service_est_monitoring_continu(service):
        raise ValueError(
            "Ce patient est en monitoring continu : les constantes viennent des machines."
        )
    mesure: dict[str, Any] = {
        "ConstanteID": f"SAISIE-{int(time.time())}",
        "Horodatage": str(payload.get("Horodatage") or pd.Timestamp.now().isoformat(timespec="minutes")),
        "source": "saisie_infirmiere",
        "note": str(payload.get("note") or "").strip()[:200] or None,
    }
    for key in _VITAL_KEYS_SAISIE:
        raw = payload.get(key)
        if raw is None or raw == "":
            continue
        try:
            mesure[key] = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Valeur invalide pour {key}") from exc
    if sum(1 for k in _VITAL_KEYS_SAISIE if mesure.get(k) is not None) < 2:
        raise ValueError("Indiquez au moins deux constantes.")
    bucket = store.constantes_manueles.setdefault(str(sejour_id), [])
    bucket.append(mesure)
    # Index plan d’étages : dernière valeur connue immédiatement
    store.dernieres_vitals_by_sej[str(sejour_id)] = {
        k: mesure[k] for k in _VITAL_KEYS_SAISIE if mesure.get(k) is not None
    }
    return _vitals_live_pour_sejour(store, sejour_id, service)


def moniteur_sejour(sejour_id: str) -> dict[str, Any]:
    """Payload léger pour graphiques / cartes (polling si monitoring continu)."""
    store = get_store()
    scored = _score_row(store, sejour_id)
    return _vitals_live_pour_sejour(store, sejour_id, scored["service"])


def predict_sejour(sejour_id: str) -> dict:
    store = get_store()
    row = store.features.loc[store.features["SejourID"] == sejour_id]
    if row.empty:
        raise KeyError(f"Séjour introuvable: {sejour_id}")
    scored = _score_row(store, sejour_id)
    doc_row = store.docs.loc[store.docs["SejourID"] == sejour_id]
    document = str(doc_row["document"].iloc[0]) if len(doc_row) else ""
    justification = grounded_justification(document) if document else "Pas de note dans le dossier."
    backend = "extrait du dossier"
    if document and llm_obligatoire():
        store.try_start_llm()
        if store.llm is not None:
            justification = generate_justification(store.llm, document)
            backend = "assistant local (LLM)"
        else:
            backend = f"extrait (LLM: {store.llm_statut})"
    feature_values = {
        c: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v))
        for c, v in row.drop(columns=[*ID_COLS, TARGET_COL, SPLIT_COL], errors="ignore")
        .iloc[0]
        .items()
    }
    top_shap = []
    max_shap = 0.0
    for row_shap in store.shap.head(8).to_dict(orient="records"):
        feat = str(row_shap.get("feature", ""))
        mag = float(row_shap.get("mean_abs_shap") or 0)
        max_shap = max(max_shap, mag)
        raw_val = feature_values.get(feat)
        if raw_val is None and feat in row.columns:
            raw_val = row[feat].iloc[0]
        if feat == "Sexe":
            valeur = f"{libelle_sexe(raw_val)} ({format_feature_value(raw_val)})"
        else:
            valeur = format_feature_value(raw_val)
        top_shap.append(
            {
                "feature": feat,
                "libelle": libelle_feature(feat),
                "mean_abs_shap": mag,
                "valeur": valeur,
            }
        )
    for item in top_shap:
        item["bar_pct"] = (
            round(100.0 * item["mean_abs_shap"] / max_shap) if max_shap > 0 else 0
        )
    proba_pct = round(scored["proba"] * 100)
    seuil_pct = round(scored["seuil"] * 100)
    X_row, _, _ = split_xy(row)
    modele = scored["modele"]
    facteurs_locaux = facteurs_risque_patient(
        modele=modele,
        bundle=store.bundle,
        X_row=X_row,
    )
    explication_risque_30j = build_explication_risque_30j(
        proba_pct=proba_pct,
        seuil_pct=seuil_pct,
        alerte=scored["alerte"],
        facteurs=facteurs_locaux,
    )
    service = scored["service"]
    loc = localisation_pour(sejour_id, service)
    moniteur = _vitals_live_pour_sejour(store, sejour_id, service)
    vitals = moniteur["constantes"]
    vitals_alert_flags = moniteur["constantes_alerte"]
    machines = moniteur["alertes_machines"]
    urgence_demo = moniteur["urgence_pedagogique"]
    urgence_restant_s = moniteur["urgence_restant_s"]
    news = moniteur["score_news"]
    charts = moniteur["series"]
    pat = _patient_card(store, scored["patient"])
    admin = _sejour_admin(store, sejour_id)
    terr = _territoire_card(store, pat["Commune"], pat["CodePostal"])
    poids_manuel = vitals.get("PoidsKg") if vitals else None
    poids = (
        round(float(poids_manuel), 1)
        if poids_manuel is not None
        else _poids_patient(store, scored["patient"])
    )
    medicaments = _medicaments_sejour(store, sejour_id)
    hist = _historique_enrichi_saisies(store, sejour_id)
    return {
        "SejourID": sejour_id,
        "PatientID": scored["patient"],
        "IPP": scored["patient"],
        "NDA": sejour_id,
        "NomFamille": pat["NomFamille"],
        "Prenom": pat["Prenom"],
        "Sexe": pat["Sexe"],
        "SexeLibelle": pat["SexeLibelle"],
        "Antecedents": pat["Antecedents"],
        "RegimeAssurance": pat["RegimeAssurance"],
        "Commune": pat["Commune"],
        "CodePostal": pat["CodePostal"],
        "PoidsKg": poids,
        "medicaments": medicaments,
        "chambre": loc["chambre"],
        "lit": loc["lit"],
        "lit_complet": loc["lit_complet"],
        "etage": loc["etage"],
        "etage_libelle": loc["etage_libelle"],
        "aile": loc["aile"],
        "uf": loc["uf"],
        "poste": loc["poste"],
        "ide_equipe": loc["ide_equipe"],
        "service": service,
        "service_libelle": SERVICE_LABELS.get(service, service),
        "monitoring_continu": moniteur["monitoring_continu"],
        "mode_monitoring": moniteur["mode_monitoring"],
        "admin": admin,
        "territoire": terr,
        "score_news": news,
        "n_meds": None if pd.isna(scored.get("n_meds")) else int(scored["n_meds"]),
        "n_diag": None if pd.isna(scored.get("n_diag")) else int(scored["n_diag"]),
        "age": None if pd.isna(scored["age"]) else round(float(scored["age"])),
        "split": scored["split"],
        "label_observe": scored["label"],
        "modele_retenu": scored["modele"],
        "proba_readmission_30j": round(scored["proba"], 4),
        "proba_pct": proba_pct,
        "seuil": round(scored["seuil"], 4),
        "seuil_pct": seuil_pct,
        "alerte_suivi_renforce": scored["alerte"],
        "niveau": "élevé" if scored["alerte"] else "faible",
        "top_shap_global": top_shap,
        "facteurs_risque_patient": facteurs_locaux,
        "explication_risque_30j": explication_risque_30j,
        "valeurs_sejour": feature_values,
        "compte_rendu_masque": document[:1200],
        "justification": justification,
        "justification_backend": backend,
        "constantes": vitals,
        "constantes_alerte": vitals_alert_flags,
        "constantes_historique": hist,
        "constantes_charts": charts,
        "tendance_constantes": moniteur["tendance_constantes"],
        "alertes_machines": machines,
        "urgence_pedagogique": urgence_demo,
        "urgence_restant_s": urgence_restant_s,
        "moniteur_refresh_seconds": moniteur["refresh_seconds"],
        "consigne": message_soignant(
            chambre=loc["chambre"],
            vitals=vitals,
            machine_alerts=machines,
            risque_sortie=scored["alerte"],
            document=document,
        ),
        "avertissement": (
            "Exercice pédagogique avec données inventées. "
            "Le prénom et la personne à prévenir ne sont pas affichés. "
            "Les constantes évoluent lentement (comme un moniteur d’étage). "
            "Cela ne remplace pas le jugement soignant."
        ),
    }


# Ambre à l’étage : seuil plus exigeant que le F2 ML (0.35),
# sinon presque la moitié des lits seraient « à surveiller ».
SEUIL_ETAGE_SURVEILLANCE = 0.50


def _cap_urgents_service(rooms: list[dict]) -> list[dict]:
    """Au plus MAX_URGENT_PAR_SERVICE urgences machine par service."""
    urgents = [r for r in rooms if r.get("niveau") == "urgent" and not r.get("vide")]
    if len(urgents) <= MAX_URGENT_PAR_SERVICE:
        return rooms
    urgents_sorted = sorted(
        urgents,
        key=lambda r: (
            (r.get("constantes") or {}).get("SpO2") or 100,
            r.get("SejourID") or "",
        ),
    )
    garder = {r["SejourID"] for r in urgents_sorted[:MAX_URGENT_PAR_SERVICE]}
    out = []
    for r in rooms:
        if r.get("niveau") == "urgent" and r.get("SejourID") not in garder:
            demote = dict(r)
            demote["niveau"] = (
                "a_surveiller"
                if (demote.get("proba") or 0) >= SEUIL_ETAGE_SURVEILLANCE
                else "calme"
            )
            demote["alertes"] = []
            demote["consigne"] = (
                f"Chambre {demote['chambre']} : constantes sous surveillance, "
                "pas d’alerte prioritaire pour le moment."
            )
            out.append(demote)
        else:
            out.append(r)
    return out


def _lit_key(service: str, chambre: str, lit: str) -> tuple[str, str, str]:
    return (str(service), str(chambre), str(lit))


def _ensure_deces_assignes(store: DemoStore) -> None:
    """Place 1 lit « décès → à nettoyer » par service du plan (démo)."""
    if store._deces_init:
        return
    store._deces_init = True
    deces = store.sejours_view.loc[store.sejours_view["ModeSortie"] == "Deces"]
    for svc in SERVICE_LABELS:
        source = SERVICE_DATA_SOURCE.get(svc, svc)
        grp = deces.loc[deces["Service"] == source]
        slots = slots_lits_service(svc)
        pris = set()
        cohorte = sejours_pour_service(
            svc,
            store.features.loc[store.features["Service"] == source, "SejourID"]
            .astype(str)
            .tolist(),
        )
        for sej in cohorte:
            loc = localisation_pour(str(sej), svc)
            pris.add((loc["chambre"], loc["lit"]))
        libre = [s for s in slots if (s["chambre"], s["lit"]) not in pris]
        if not libre or grp.empty:
            continue
        slot = libre[0]
        sej = str(grp["SejourID"].iloc[0])
        store.deces_assignes[_lit_key(svc, slot["chambre"], slot["lit"])] = sej


def _service_code_from_label(label: str) -> str | None:
    for code, lib in SERVICE_LABELS.items():
        if lib == label or code == label:
            return code
    return label if label in SERVICE_LABELS else None


def _room_deces(store: DemoStore, service: str, slot: dict, sej: str) -> dict:
    row = store.sejours_view.loc[store.sejours_view["SejourID"] == sej]
    pid = str(row["PatientID"].iloc[0]) if len(row) else ""
    pat = _patient_card(store, pid) if pid else {
        "NomFamille": "—",
        "Sexe": "—",
        "SexeLibelle": "Non renseigné",
    }
    return {
        "SejourID": sej,
        "PatientID": pid,
        "NomFamille": pat["NomFamille"],
        "Sexe": pat.get("Sexe"),
        "SexeLibelle": pat.get("SexeLibelle"),
        "chambre": slot["chambre"],
        "lit": slot["lit"],
        "etage": slot["etage"],
        "etage_libelle": slot["etage_libelle"],
        "aile": slot["aile"],
        "poste": slot["poste"],
        "uf": slot["uf"],
        "service": slot["service"],
        "service_code": service,
        "niveau": "a_nettoyer",
        "vide": True,
        "deces": True,
        "proba": None,
        "constantes": {},
        "tendance": None,
        "alertes": [],
        "consigne": (
            f"Lit {slot['chambre']}{slot['lit']} : patient décédé. "
            "Chambre à nettoyer avant nouvelle admission."
        ),
        "score_news": None,
        "age": None,
    }


def _room_disponible(service: str, slot: dict) -> dict:
    return {
        "SejourID": None,
        "PatientID": None,
        "NomFamille": None,
        "Sexe": None,
        "SexeLibelle": None,
        "chambre": slot["chambre"],
        "lit": slot["lit"],
        "etage": slot["etage"],
        "etage_libelle": slot["etage_libelle"],
        "aile": slot["aile"],
        "poste": slot["poste"],
        "uf": slot["uf"],
        "service": slot["service"],
        "service_code": service,
        "niveau": "disponible",
        "vide": True,
        "deces": False,
        "proba": None,
        "constantes": {},
        "tendance": None,
        "alertes": [],
        "consigne": f"Lit {slot['chambre']}{slot['lit']} libre — disponible.",
        "score_news": None,
        "age": None,
    }


def _build_occupe_room(
    store: DemoStore, sej: str, sc: dict, loc: dict, tick: int, *, service_code: str
) -> dict:
    continu = service_est_monitoring_continu(service_code)
    if continu:
        profil = store.vitals_by_sej.get(sej)
        vitals = snapshot_constantes(profil, tick=tick)
        tendance = tendance_constantes(profil, tick=tick)
    else:
        profil = None
        vitals = _vitals_manuel_courants(store, sej)
        tendance = "stable"
    machines = alertes_machines(vitals) if vitals else []
    doc_row = store.docs.loc[store.docs["SejourID"] == sej]
    document = str(doc_row["document"].iloc[0]) if len(doc_row) else ""
    suivi_sortie = bool(sc["proba"] >= SEUIL_ETAGE_SURVEILLANCE)
    msg = message_soignant(
        chambre=loc["chambre"],
        vitals=vitals or {},
        machine_alerts=machines,
        risque_sortie=suivi_sortie,
        document=document,
    )
    if not continu and not machines:
        msg = (
            f"Chambre {loc['chambre']} : constantes saisies par l’équipe "
            "(pas de moniteur branché)."
        )
    niveau = "calme"
    if suivi_sortie:
        niveau = "a_surveiller"
    # Alertes machines (SpO2 etc.) uniquement pertinentes en monitoring continu
    if continu and machines:
        niveau = "urgent"
    elif (not continu) and machines:
        niveau = "a_surveiller"
    pat = _patient_card(store, sc["patient"])
    return {
        "SejourID": sej,
        "PatientID": sc["patient"],
        "NomFamille": pat["NomFamille"],
        "Sexe": pat["Sexe"],
        "SexeLibelle": pat["SexeLibelle"],
        "chambre": loc["chambre"],
        "lit": loc["lit"],
        "etage": loc["etage"],
        "etage_libelle": loc["etage_libelle"],
        "aile": loc["aile"],
        "poste": loc["poste"],
        "uf": loc["uf"],
        "service": SERVICE_LABELS.get(service_code, service_code),
        "service_code": service_code,
        "monitoring_continu": continu,
        "niveau": niveau,
        "vide": False,
        "deces": False,
        "proba": round(sc["proba"], 3),
        "constantes": vitals,
        "tendance": tendance,
        "alertes": machines if continu else [],
        "consigne": msg,
        "score_news": score_news_simplifie(vitals) if vitals else None,
        "age": None if pd.isna(sc["age"]) else round(float(sc["age"])),
    }


def nettoyer_lit(*, service: str, chambre: str, lit: str) -> dict:
    """Marque un lit post-décès comme nettoyé → disponible."""
    store = get_store()
    code = _service_code_from_label(service) or service
    key = _lit_key(code, chambre, lit)
    if key not in store.deces_assignes:
        raise KeyError("Lit non marqué décès / à nettoyer")
    store.lits_nettoyes.add(key)
    return {"ok": True, "chambre": chambre, "lit": lit, "etat": "disponible"}


def admettre_lit(*, service: str, chambre: str, lit: str) -> dict:
    """Remplit un lit disponible avec un séjour de la cohorte (démo auto)."""
    store = get_store()
    code = _service_code_from_label(service) or service
    key = _lit_key(code, chambre, lit)
    if key in store.deces_assignes and key not in store.lits_nettoyes:
        raise KeyError("Nettoyer le lit avant d’admettre un patient")
    if key in store.admissions_demo:
        return {"ok": True, "SejourID": store.admissions_demo[key], "deja": True}

    pris_sej = set(store.admissions_demo.values())
    source = SERVICE_DATA_SOURCE.get(code, code)
    naturels = []
    vus: set[tuple[str, str]] = set()
    pool = sejours_pour_service(
        code,
        store.features.loc[store.features["Service"] == source, "SejourID"]
        .astype(str)
        .tolist(),
    )
    for sej in pool:
        loc = localisation_pour(sej, code)
        cle = (loc["chambre"], loc["lit"])
        if cle in vus:
            continue
        vus.add(cle)
        naturels.append(sej)
        if len(naturels) >= MAX_LITS_PAR_SERVICE:
            break
    pris_sej.update(naturels)

    restants = [s for s in pool if s not in pris_sej]
    if not restants:
        restants = [
            s
            for s in store.features["SejourID"].astype(str).tolist()
            if s not in pris_sej
        ]
    if not restants:
        raise KeyError("Plus de patient disponible pour la démo")

    sej = restants[0]
    store.admissions_demo[key] = sej
    store.lits_nettoyes.add(key)
    return {
        "ok": True,
        "SejourID": sej,
        "chambre": chambre,
        "lit": lit,
        "etat": "occupe",
        "href": f"/soignant/sejours/{sej}",
    }


def _lits_vides(service: str, occupes: set[tuple[str, str]]) -> list[dict]:
    """Lits physiques non occupés : décès à nettoyer, ou disponibles (+)."""
    store = get_store()
    _ensure_deces_assignes(store)
    out = []
    for slot in slots_lits_service(service):
        cle = (slot["chambre"], slot["lit"])
        if cle in occupes:
            continue
        key = _lit_key(service, slot["chambre"], slot["lit"])
        if key in store.admissions_demo:
            continue
        if key in store.deces_assignes and key not in store.lits_nettoyes:
            out.append(_room_deces(store, service, slot, store.deces_assignes[key]))
        else:
            out.append(_room_disponible(service, slot))
    return out


def _rooms_for_service(
    store: DemoStore,
    service: str,
    tick: int,
    *,
    max_par_service: int,
) -> list[dict]:
    source = SERVICE_DATA_SOURCE.get(service, service)
    cohorte = sejours_pour_service(
        service,
        store.features.loc[store.features["Service"] == source, "SejourID"]
        .astype(str)
        .tolist(),
    )
    candidats = []
    for sej in cohorte:
        sc = _score_row(store, sej)
        loc = localisation_pour(sej, service)
        candidats.append((loc["chambre"], loc["lit"], sej, sc, loc))
    candidats.sort(key=lambda x: (x[0], x[1], x[2]))
    vus: set[tuple[str, str]] = set()
    choisis = []
    cap = min(max_par_service, MAX_LITS_PAR_SERVICE)
    for chambre, lit, sej, sc, loc in candidats:
        cle = (chambre, lit)
        if cle in vus:
            continue
        vus.add(cle)
        choisis.append((sej, sc, loc))
        if len(choisis) >= cap:
            break

    rooms: list[dict] = []
    occupes: set[tuple[str, str]] = set()
    for sej, sc, loc in choisis:
        rooms.append(
            _build_occupe_room(store, sej, sc, loc, tick, service_code=service)
        )
        occupes.add((loc["chambre"], loc["lit"]))

    for key, sej in list(store.admissions_demo.items()):
        svc, chambre, lit = key
        if svc != service:
            continue
        if (chambre, lit) in occupes:
            continue
        if sej not in set(store.features["SejourID"].astype(str)):
            continue
        sc = _score_row(store, sej)
        loc = localisation_pour(sej, service)
        loc = dict(loc)
        loc["chambre"] = chambre
        loc["lit"] = lit
        loc["lit_complet"] = f"{chambre}{lit}"
        room = _build_occupe_room(store, sej, sc, loc, tick, service_code=service)
        rooms.append(room)
        occupes.add((chambre, lit))

    rooms = _cap_urgents_service(rooms)
    rooms.extend(_lits_vides(service, occupes))
    return sorted(
        rooms,
        key=lambda r: (
            r["chambre"],
            r["lit"],
            0 if r["niveau"] == "a_nettoyer" else (1 if r.get("vide") else 0),
        ),
    )


def live_board(*, max_par_service: int | None = None) -> dict:
    store = get_store()
    tick = current_tick()
    cycle, urgence_active, urgence_restant_s = fenetre_urgence_pedagogique()
    cap = max_par_service if max_par_service is not None else MAX_LITS_PAR_SERVICE
    plan_etages: list[dict] = []
    etages_ordonnes: dict[str, list] = {}

    for floor in FLOOR_PLAN:
        etage_lib = floor["etage_libelle"]
        floor_rooms: list[dict] = []
        services_out: list[dict] = []
        for svc in floor["services"]:
            rooms = _rooms_for_service(
                store, svc, tick, max_par_service=cap
            )
            meta = UNITE_PAR_SERVICE[svc]
            services_out.append(
                {
                    "code": svc,
                    "nom": SERVICE_LABELS[svc],
                    "uf": meta["uf"],
                    "aile": meta["aile"],
                    "poste": meta["poste"],
                    "equipe": equipe_complete(svc, floor["etage"]),
                    "lits": rooms,
                    "lits_total": MAX_LITS_PAR_SERVICE,
                }
            )
            floor_rooms.extend(rooms)

        pedago = appliquer_urgence_pedagogique(
            floor_rooms,
            etage_libelle=etage_lib,
            cycle=cycle,
            active=urgence_active,
        )
        pedago_by_svc: dict[str, list[dict]] = {}
        for room in pedago:
            code = str(room.get("service_code") or "")
            pedago_by_svc.setdefault(code, []).append(room)

        for svc_block in services_out:
            svc_block["lits"] = sorted(
                pedago_by_svc.get(svc_block["code"], svc_block["lits"]),
                key=lambda r: (r["chambre"], r["lit"]),
            )

        etages_ordonnes[etage_lib] = sorted(
            pedago,
            key=lambda r: (
                r["chambre"],
                r["lit"],
                0 if r["niveau"] == "a_nettoyer" else (1 if r.get("vide") else 0),
            ),
        )
        plan_etages.append(
            {
                "etage": floor["etage"],
                "etage_libelle": etage_lib,
                "medecin": libelle_personne(MEDECIN_PAR_ETAGE[floor["etage"]]),
                "services": services_out,
            }
        )

    fil = []
    for rooms in etages_ordonnes.values():
        for room in rooms:
            if room["niveau"] in {"urgent", "a_surveiller"} and not room.get("vide"):
                fil.append(
                    {
                        "chambre": room["chambre"],
                        "lit": room["lit"],
                        "service": room["service"],
                        "NomFamille": room["NomFamille"],
                        "niveau": room["niveau"],
                        "texte": room["consigne"],
                        "href": f"/soignant/sejours/{room['SejourID']}",
                    }
                )
    fil.sort(key=lambda x: 0 if x["niveau"] == "urgent" else 1)
    # LLM étage : brief IA sur la 1ʳᵉ urgence (async → cache, ne bloque pas le monitoring)
    assistant = ""
    assistant_en_cours = False
    top_urgent = next((x for x in fil if x["niveau"] == "urgent"), None)
    if top_urgent and llm_obligatoire():
        store.try_start_llm()
        top = top_urgent
        key = f"brief|{top['href']}"
        if key in store.llm_cache:
            assistant = store.llm_cache[key]
        else:
            sej = top["href"].rsplit("/", 1)[-1]
            vitals = snapshot_constantes(store.vitals_by_sej.get(sej), tick=tick)
            doc_row = store.docs.loc[store.docs["SejourID"] == sej]
            document = str(doc_row["document"].iloc[0]) if len(doc_row) else ""
            if store.llm is not None:
                store.enqueue_brief(key, top["chambre"], vitals, document)
                assistant_en_cours = key in store._llm_jobs
                assistant = "Analyse IA du dossier en cours…"
            else:
                assistant = f"IA locale : {store.llm_statut}"
    n_urgent = sum(1 for x in fil if x["niveau"] == "urgent")
    n_watch = sum(1 for x in fil if x["niveau"] == "a_surveiller")
    if urgence_active:
        rythme = (
            f"Phase alerte ({urgence_restant_s} s) — "
            "1 urgence prioritaire par étage, puis 1 min de calme."
        )
    else:
        rythme = (
            f"Phase calme ({urgence_restant_s} s) — "
            "aucune urgence machine ; prochaine alerte dans un instant."
        )
    return {
        "tick": tick,
        "horloge": time.strftime("%H:%M:%S"),
        "etages": etages_ordonnes,
        "plan_etages": plan_etages,
        "fil_alertes": fil[:12],
        "n_urgent": n_urgent,
        "n_watch": n_watch,
        "assistant": assistant,
        "assistant_actif": bool(llm_obligatoire()),
        "assistant_en_cours": assistant_en_cours,
        "llm_statut": store.llm_statut,
        "hopital": "CHU CISIA — poste de soins (démo)",
        "urgence_cycle": cycle,
        "urgence_active": urgence_active,
        "urgence_restant_s": urgence_restant_s,
        "rythme_pedagogique": rythme,
    }


def registre_rows(
    *, sensibilite: str = "", usage: str = "", origine: str = ""
) -> list[dict]:
    store = get_store()
    df = store.registre.copy()
    if sensibilite:
        df = df.loc[df["sensibilite"] == sensibilite]
    if usage:
        df = df.loc[
            (df["usage_score_sortie"] == usage) | (df["usage_score_tele"] == usage)
        ]
    if origine and "origine_donnee" in df.columns:
        df = df.loc[df["origine_donnee"] == origine]
    return df.to_dict(orient="records")


def _registre_label(field: str, value: str) -> str:
    maps = {
        "sensibilite": {
            "identite_directe": "Identité directe",
            "sante_art9": "Santé (art. 9)",
            "proxy_socio": "Proxy socio-éco.",
            "faible": "Faible",
            "aucune": "Aucune",
        },
        "usage": {
            "autorise": "Autorisé",
            "flag_only": "Surveillance",
            "exclu": "Exclu",
        },
        "origine": {
            "sujet": "Sujet",
            "insee_ajoute": "INSEE ajouté",
            "derive_affichage": "Dérivé affichage",
        },
    }
    return maps.get(field, {}).get(value, value)


def registre_report(
    *, sensibilite: str = "", usage: str = "", origine: str = ""
) -> dict:
    """Registre RGPD structuré pour l’interface (stats + groupes par fichier)."""
    store = get_store()
    all_rows = store.registre.to_dict(orient="records")
    filtered = registre_rows(sensibilite=sensibilite, usage=usage, origine=origine)

    enriched = []
    for row in filtered:
        orig = str(row.get("origine_donnee") or "sujet")
        enriched.append(
            {
                **row,
                "origine_donnee": orig,
                "origine_label": _registre_label("origine", orig),
                "sensibilite_label": _registre_label("sensibilite", str(row.get("sensibilite", ""))),
                "usage_sortie_label": _registre_label(
                    "usage", str(row.get("usage_score_sortie", ""))
                ),
                "usage_tele_label": _registre_label(
                    "usage", str(row.get("usage_score_tele", ""))
                ),
            }
        )

    files: dict[str, list[dict]] = {}
    for row in enriched:
        fichier = str(row.get("fichier_source", "—"))
        files.setdefault(fichier, []).append(row)

    file_groups = [
        {"fichier": nom, "rows": rows, "count": len(rows)}
        for nom, rows in sorted(files.items())
    ]

    def _count(field: str, value: str) -> int:
        return sum(1 for r in all_rows if str(r.get(field, "")) == value)

    return {
        "total_all": len(all_rows),
        "total_filtered": len(filtered),
        "stats": {
            "insee": _count("origine_donnee", "insee_ajoute"),
            "sujet": _count("origine_donnee", "sujet"),
            "derive": _count("origine_donnee", "derive_affichage"),
            "autorise_sortie": _count("usage_score_sortie", "autorise"),
            "exclu_sortie": _count("usage_score_sortie", "exclu"),
        },
        "file_groups": file_groups,
        "rows": filtered,
        "filters": {
            "sensibilite": sensibilite,
            "usage": usage,
            "origine": origine,
        },
    }


def biais_rows(*, score: str = "sortie") -> list[dict]:
    """Lit les CSV de biais déjà calculés (sortie ou télé)."""
    store = get_store()
    name = "score_sortie_biais.csv" if score != "tele" else "score_tele_biais.csv"
    path = store.paths.models / name
    if not path.exists():
        return []
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def _biais_pct(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val) * 100, 1)


def _biais_label(category: str, raw: str) -> str:
    labels = {
        "F": "Femme",
        "M": "Homme",
        ">80": "Plus de 80 ans",
        "65-80": "65–80 ans",
        "<65": "Moins de 65 ans",
        "T3_eleve": "Indice T3 (élevé)",
        "T2": "Indice T2",
        "T1_faible": "Indice T1 (faible)",
    }
    if category == "Sexe":
        return labels.get(raw, raw)
    if category == "age":
        return labels.get(raw, raw)
    if category == "defav":
        return labels.get(raw, raw)
    return raw


def _biais_category_meta(category: str) -> dict:
    meta = {
        "Sexe": {"title": "Sexe", "icon": "groups", "description": "Écart de performance entre femmes et hommes."},
        "age": {"title": "Âge", "icon": "calendar_month", "description": "Performance par tranche d’âge à la sortie."},
        "defav": {"title": "Territoire", "icon": "map", "description": "Écart selon l’indice de défavorisation de la commune."},
    }
    return meta.get(category, {"title": category, "icon": "analytics", "description": ""})


def biais_report(*, score: str = "sortie") -> dict:
    """Structure le rapport de biais par catégorie pour l’interface."""
    store = get_store()
    raw_rows = biais_rows(score=score)
    buckets: dict[str, list[dict]] = {}
    for row in raw_rows:
        groupe = str(row.get("groupe", ""))
        if "=" in groupe:
            category, label_raw = groupe.split("=", 1)
        else:
            category, label_raw = "autre", groupe
        enriched = {
            **row,
            "groupe": groupe,
            "label": _biais_label(category, label_raw),
            "prevalence_pct": _biais_pct(row.get("prevalence")),
            "rappel_pct": _biais_pct(row.get("rappel")),
            "taux_alerte_pct": _biais_pct(row.get("taux_alerte")),
        }
        buckets.setdefault(category, []).append(enriched)

    order = ["Sexe", "age", "defav"]
    categories = []
    for cat in order:
        if cat not in buckets:
            continue
        meta = _biais_category_meta(cat)
        categories.append({**meta, "id": cat, "rows": buckets[cat]})
    for cat, rows in buckets.items():
        if cat in order:
            continue
        meta = _biais_category_meta(cat)
        categories.append({**meta, "id": cat, "rows": rows})

    total_n = sum(int(r.get("n") or 0) for r in raw_rows)
    rappels = [_biais_pct(row.get("rappel")) for row in raw_rows]
    rappels = [p for p in rappels if p is not None]
    recall_spread = round(max(rappels) - min(rappels), 1) if len(rappels) >= 2 else None

    score_label = "Score sortie" if score != "tele" else "Score télésurveillance"
    modele = store.metrics.get("retenu", "—")
    if score == "tele":
        tele_metrics = store.paths.models / "score_tele_metrics.json"
        if tele_metrics.exists():
            modele = json.loads(tele_metrics.read_text(encoding="utf-8")).get("retenu", modele)

    return {
        "score": score,
        "score_label": score_label,
        "modele": modele,
        "categories": categories,
        "total_groups": len(raw_rows),
        "total_n": total_n,
        "recall_spread": recall_spread,
        "rows": raw_rows,
    }


def list_sejours_cisia(
    *, q: str = "", a_risque: bool = False, page: int = 1, page_size: int = 20
) -> dict:
    """Liste orientée brief CISIA : proba, alerte, durée — pas de chambre."""
    store = get_store()
    rows = []
    for sej in store.features["SejourID"].tolist():
        sc = _score_row(store, sej)
        admin = _sejour_admin(store, sej)
        pat = _patient_card(store, sc["patient"])
        proba = float(sc["proba"])
        seuil = float(sc["seuil"])
        rows.append(
            {
                "SejourID": sej,
                "Service": sc["service"],
                "service_libelle": SERVICE_LABELS.get(sc["service"], sc["service"]),
                "NomFamille": pat["NomFamille"],
                "SexeLibelle": pat["SexeLibelle"],
                "age": None if pd.isna(sc["age"]) else int(sc["age"]),
                "DureeSejour": admin.get("DureeSejour"),
                "TypeSejour": admin.get("TypeSejour") or "—",
                "GHM": admin.get("GHM") or "—",
                "ModeSortie": admin.get("ModeSortie"),
                "proba_readmission_30j": proba,
                "proba_pct": round(proba * 100, 1),
                "seuil": seuil,
                "seuil_pct": round(seuil * 100, 1),
                "alerte_suivi_renforce": bool(sc["alerte"]),
                "split": sc["split"],
            }
        )
    df = pd.DataFrame(rows)
    total_scored = int(len(df))
    total_at_risk = int(df["alerte_suivi_renforce"].sum()) if total_scored else 0
    if q.strip():
        qq = q.strip().upper()
        df = df.loc[
            df["SejourID"].astype(str).str.upper().str.contains(qq, regex=False)
            | df["NomFamille"].astype(str).str.upper().str.contains(qq, regex=False)
        ]
    if a_risque:
        df = df.loc[df["alerte_suivi_renforce"]]
    df = df.sort_values(
        ["alerte_suivi_renforce", "proba_readmission_30j"], ascending=[False, False]
    )
    total = int(len(df))
    page = max(1, page)
    start = (page - 1) * page_size
    chunk = df.iloc[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": chunk.to_dict(orient="records"),
        "a_risque": a_risque,
        "stats": {
            "total_scored": total_scored,
            "total_at_risk": total_at_risk,
            "filtered": total,
            "modele": store.metrics.get("retenu", "—"),
        },
    }


def overview() -> dict:
    store = get_store()
    return {
        "n_sejours": int(len(store.features)),
        "prevalence": float(store.features[TARGET_COL].mean()),
        "modele_retenu": store.metrics.get("retenu"),
        "metrics_test": store.metrics.get(store.metrics.get("retenu", "logistic"), {}).get(
            "test", {}
        ),
        "llm_disponible": store.llm is not None,
        "llm_statut": store.llm_statut,
        "llm_modele": store.llm_modele,
        "bind": "127.0.0.1",
        "hopital": "CHU CISIA — poste de soins (démo)",
    }


def jury_parcours(*, sejour_exemple: str | None = None) -> dict:
    """Contenu du parcours jury / process démo (cœur CISIA)."""
    if not sejour_exemple:
        data = list_sejours_cisia(a_risque=True, page=1, page_size=1)
        if data["items"]:
            sejour_exemple = str(data["items"][0]["SejourID"])
        else:
            data = list_sejours_cisia(page=1, page_size=1)
            sejour_exemple = (
                str(data["items"][0]["SejourID"]) if data["items"] else None
            )
    href_fiche = (
        f"/cisia/sejours/{sejour_exemple}" if sejour_exemple else "/cisia/sejours"
    )
    steps = [
        {
            "n": 1,
            "icon": "monitoring",
            "titre_court": "Score",
            "titre": "Comprendre le modèle",
            "texte": (
                "Montrer le risque de réadmission à 30 jours : prévalence, modèle retenu, "
                "métriques test. Le seuil privilégie le rappel."
            ),
            "texte_court": "Prévalence, modèle logistic, seuil d’alerte.",
            "a_faire": (
                "Lisez les indicateurs ci-dessus, ouvrez les métriques si besoin, "
                "puis passez à l’étape 2."
            ),
            "href": "/cisia/sejours?a_risque=true",
            "cta": "Étape 2 — Voir les séjours à risque",
        },
        {
            "n": 2,
            "icon": "format_list_bulleted",
            "titre_court": "Séjours",
            "titre": "Repérer une sortie à risque",
            "texte": (
                "Liste filtrée « à risque ». Cliquez « Ouvrir » sur une ligne "
                "pour afficher le score détaillé."
            ),
            "texte_court": "Filtre à risque déjà prêt — un clic sur « Ouvrir ».",
            "a_faire": "Cliquez « Ouvrir » sur la première ligne (suivi renforcé = Oui).",
            "href": "/cisia/sejours?a_risque=true",
            "cta": "Aller à la liste filtrée",
        },
        {
            "n": 3,
            "icon": "psychology",
            "titre_court": "Fiche",
            "titre": "Expliquer une décision",
            "texte": (
                "Sur la fiche : score → SHAP → justification IA locale (CR masqué). "
                "Rien n’est envoyé sur Internet."
            ),
            "texte_court": "Score, facteurs SHAP, justification locale.",
            "a_faire": "Parcourez les blocs 1→4, puis enchaînez vers les biais.",
            "href": href_fiche,
            "cta": "Ouvrir la fiche d’exemple",
        },
        {
            "n": 4,
            "icon": "balance",
            "titre_court": "Biais",
            "titre": "Mesurer les écarts",
            "texte": (
                "Biais par sexe, âge et défavorisation. On mesure les écarts, "
                "on ne les cache pas."
            ),
            "texte_court": "Table des biais du modèle retenu.",
            "a_faire": "Montrez un écart (ex. âge), puis allez au registre.",
            "href": "/cisia/biais",
            "cta": "Voir les biais",
        },
        {
            "n": 5,
            "icon": "shield",
            "titre_court": "Registre",
            "titre": "RGPD et traçabilité",
            "texte": (
                "Registre : sensibilité, usage score, origine sujet vs INSEE. "
                "Clôture privacy."
            ),
            "texte_court": "Qui a le droit d’utiliser quelles données.",
            "a_faire": "Filtrez « INSEE ajouté », puis terminez la démo.",
            "href": "/cisia/registre?origine=insee_ajoute",
            "cta": "Ouvrir le registre",
        },
    ]
    return {"steps": steps, "sejour_exemple": sejour_exemple}


def process_demo_context(
    *, path: str = "", sejour_id: str | None = None, tutorial_active: bool = False
) -> dict:
    """Barre de process + consignes — uniquement si tutoriel actif (1ère connexion)."""
    data = jury_parcours(sejour_exemple=sejour_id)
    sejour = data["sejour_exemple"]
    if not tutorial_active:
        return {
            "process_step": 0,
            "process_total": 5,
            "process_tip": "",
            "process_suivant": None,
            "demo_spotlight": None,
            "demo_spotlight_hint": None,
            "sejour_exemple": sejour,
            "steps": data["steps"],
            "demo_tutorial": False,
        }
    href_fiche = f"/cisia/sejours/{sejour}" if sejour else "/cisia/sejours"
    if path.startswith("/cisia/sejours/") and sejour_id:
        step = 3
        tip = (
            "Parcourez score → SHAP → justification. "
            "Puis cliquez « Étape suivante » pour les biais."
        )
        suivant = {"label": "Étape 4 — Biais", "href": "/cisia/biais"}
        spotlight = "score-panel"
        spotlight_hint = "Score de risque et seuil d’alerte"
    elif path.startswith("/cisia/sejours"):
        step = 2
        tip = (
            "Le filtre « à risque » est actif. "
            "Cliquez « Ouvrir » sur la première ligne (Oui)."
        )
        suivant = {"label": "Étape 3 — Fiche d’exemple", "href": href_fiche}
        spotlight = "open-sejour"
        spotlight_hint = "Ouvrir ce séjour à risque"
    elif path.startswith("/cisia/biais"):
        step = 4
        tip = "Montrez un groupe (âge ou sexe), puis ouvrez le registre RGPD."
        suivant = {
            "label": "Étape 5 — Registre",
            "href": "/cisia/registre?origine=insee_ajoute",
        }
        spotlight = "biais-age"
        spotlight_hint = "Écart de performance par tranche d’âge"
    elif path.startswith("/cisia/registre"):
        step = 5
        tip = (
            "Filtrez par origine / sensibilité. Démo CISIA terminée — "
            "option : démo soignant."
        )
        suivant = {"label": "Option · Démo soignant", "href": "/soignant"}
        spotlight = "registre-filtre"
        spotlight_hint = "Filtrer les sources INSEE ajoutées"
    elif path.startswith("/cisia/jury"):
        step = 0
        tip = (
            "Parcours guidé prêt. Appuyez sur Entrée pour démarrer "
            "la visite des 5 étapes CISIA."
        )
        suivant = {"label": "Étape 1 — Accueil CISIA", "href": "/cisia"}
        spotlight = "process-next"
        spotlight_hint = "Démarrer le parcours guidé"
    else:
        step = 1
        tip = "Lisez les indicateurs, puis lancez l’étape 2 (séjours à risque)."
        suivant = {
            "label": "Étape 2 — Séjours à risque",
            "href": "/cisia/sejours?a_risque=true",
        }
        spotlight = "process-next"
        spotlight_hint = "Lancer l’étape 2 — séjours à risque"
    return {
        "process_step": step,
        "process_total": 5,
        "process_tip": tip,
        "process_suivant": suivant,
        "demo_spotlight": spotlight,
        "demo_spotlight_hint": spotlight_hint,
        "sejour_exemple": sejour,
        "steps": data["steps"],
        "demo_tutorial": True,
    }

