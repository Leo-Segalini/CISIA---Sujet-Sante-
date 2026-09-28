from __future__ import annotations

import hashlib
import math
import time
from typing import Any

import pandas as pd

SERVICE_LABELS = {
    "Urgences": "Urgences",
    "Observation": "Observation courte",
    "SoinsContinus": "Soins continus",
    "Infectieux": "Infectiologie",
    "Cardiologie": "Cardiologie",
    "Pneumologie": "Pneumologie",
    "MedecineInterne": "Médecine interne",
    "Gastroenterologie": "Gastro-entérologie",
    "Chirurgie": "Chirurgie viscérale",
    "Orthopedie": "Orthopédie",
}

# Monitoring machine en continu (USC / réanimation).
# Les autres services = saisie infirmière manuelle (pas de branchement live).
SERVICES_MONITORING_CONTINU: frozenset[str] = frozenset({"SoinsContinus"})


def service_est_monitoring_continu(service: str | None) -> bool:
    """True si le service a des patients branchés (moniteur live)."""
    if not service:
        return False
    return str(service) in SERVICES_MONITORING_CONTINU


def libelle_mode_monitoring(service: str | None) -> str:
    if service_est_monitoring_continu(service):
        return "Monitoring continu (machines)"
    return "Saisie infirmière (pas de branchement)"


# Service CSV source pour les unités virtuelles (répartition démo)
SERVICE_DATA_SOURCE: dict[str, str] = {
    "Observation": "Urgences",
    "Infectieux": "MedecineInterne",
    "Gastroenterologie": "MedecineInterne",
    "Orthopedie": "Chirurgie",
}

# 2 services par étage · 12 lits max / service (6 ch. × 2 lits)
UNITE_PAR_SERVICE: dict[str, dict[str, Any]] = {
    "Urgences": {
        "etage": 0,
        "aile": "Aile A",
        "uf": "UF-SAU",
        "poste": "SAU",
        "chambre_offset": 0,
    },
    "Observation": {
        "etage": 0,
        "aile": "Aile A",
        "uf": "UF-OBS",
        "poste": "Obs RDC",
        "chambre_offset": 6,
    },
    "SoinsContinus": {
        "etage": 1,
        "aile": "Aile B",
        "uf": "UF-USC",
        "poste": "USC",
        "chambre_offset": 0,
    },
    "Infectieux": {
        "etage": 1,
        "aile": "Aile B",
        "uf": "UF-INF",
        "poste": "Infectieux",
        "chambre_offset": 6,
    },
    "Cardiologie": {
        "etage": 2,
        "aile": "Aile C",
        "uf": "UF-CAR",
        "poste": "Cardio",
        "chambre_offset": 0,
    },
    "Pneumologie": {
        "etage": 2,
        "aile": "Aile D",
        "uf": "UF-PNE",
        "poste": "Pneumo",
        "chambre_offset": 6,
    },
    "MedecineInterne": {
        "etage": 3,
        "aile": "Aile E",
        "uf": "UF-MED",
        "poste": "Méd. interne",
        "chambre_offset": 0,
    },
    "Gastroenterologie": {
        "etage": 3,
        "aile": "Aile E",
        "uf": "UF-GAS",
        "poste": "Gastro",
        "chambre_offset": 6,
    },
    "Chirurgie": {
        "etage": 4,
        "aile": "Aile F",
        "uf": "UF-CHI",
        "poste": "Chirurgie",
        "chambre_offset": 0,
    },
    "Orthopedie": {
        "etage": 4,
        "aile": "Aile F",
        "uf": "UF-ORT",
        "poste": "Orthopédie",
        "chambre_offset": 6,
    },
}

FLOOR_PLAN: list[dict[str, Any]] = [
    {
        "etage": 0,
        "etage_libelle": "RDC",
        "services": ["Urgences", "Observation"],
    },
    {
        "etage": 1,
        "etage_libelle": "1er étage",
        "services": ["SoinsContinus", "Infectieux"],
    },
    {
        "etage": 2,
        "etage_libelle": "2e étage",
        "services": ["Cardiologie", "Pneumologie"],
    },
    {
        "etage": 3,
        "etage_libelle": "3e étage",
        "services": ["MedecineInterne", "Gastroenterologie"],
    },
    {
        "etage": 4,
        "etage_libelle": "4e étage",
        "services": ["Chirurgie", "Orthopedie"],
    },
]

MEDECIN_PAR_ETAGE: dict[int, dict[str, str]] = {
    0: {"prenom": "Philippe", "nom": "Moreau"},
    1: {"prenom": "Isabelle", "nom": "Garnier"},
    2: {"prenom": "Anne", "nom": "Rousseau"},
    3: {"prenom": "Martin", "nom": "Dupont"},
    4: {"prenom": "Laurent", "nom": "Mercier"},
}


def _person(prenom: str, nom: str) -> dict[str, str]:
    return {"prenom": prenom, "nom": nom}


EQUIPE_PAR_SERVICE: dict[str, dict[str, dict[str, str]]] = {
    "Urgences": {
        "infirmier": _person("Camille", "Renard"),
        "aide_soignante": _person("Julien", "Petit"),
    },
    "Observation": {
        "infirmier": _person("Émilie", "Blanchard"),
        "aide_soignante": _person("Nadia", "El Amrani"),
    },
    "SoinsContinus": {
        "infirmier": _person("Claire", "Martin"),
        "aide_soignante": _person("Sophie", "Durand"),
    },
    "Infectieux": {
        "infirmier": _person("Karim", "Benali"),
        "aide_soignante": _person("Léa", "Fontaine"),
    },
    "Cardiologie": {
        "infirmier": _person("Marine", "Lefèvre"),
        "aide_soignante": _person("Thomas", "Girard"),
    },
    "Pneumologie": {
        "infirmier": _person("Audrey", "Simon"),
        "aide_soignante": _person("Inès", "Morel"),
    },
    "MedecineInterne": {
        "infirmier": _person("Nathalie", "Roux"),
        "aide_soignante": _person("Marc", "Delacroix"),
    },
    "Gastroenterologie": {
        "infirmier": _person("Hélène", "Perrin"),
        "aide_soignante": _person("Yasmine", "Kouassi"),
    },
    "Chirurgie": {
        "infirmier": _person("Patricia", "Lambert"),
        "aide_soignante": _person("Bruno", "Caron"),
    },
    "Orthopedie": {
        "infirmier": _person("Valérie", "Meunier"),
        "aide_soignante": _person("Chloé", "Bernard"),
    },
}


def libelle_personne(person: dict[str, str] | str | None) -> str:
    """Prénom + nom pour affichage soignant."""
    if not person:
        return "—"
    if isinstance(person, str):
        return person.strip() or "—"
    prenom = str(person.get("prenom", "")).strip()
    nom = str(person.get("nom", "")).strip()
    return f"{prenom} {nom}".strip() or "—"


def equipe_complete(service: str, etage: int) -> dict[str, dict[str, str]]:
    """Médecin d'étage + IDE + AS pour un service."""
    base = EQUIPE_PAR_SERVICE.get(service, {})
    return {
        "medecin": MEDECIN_PAR_ETAGE.get(etage, _person("", "")),
        "infirmier": base.get("infirmier", _person("", "")),
        "aide_soignante": base.get("aide_soignante", _person("", "")),
    }

# Seuils d'alerte soignants (pas les bornes « aberrantes » techniques)
ALERT_RULES = {
    "SpO2": ("Saturation en oxygène", "%", 92, None, "basse"),
    "FrequenceCardiaque": ("Pouls", "/min", 50, 120, "inhabituel"),
    "TensionSystolique": ("Tension (haute)", "mmHg", 90, 180, "inhabituelle"),
    "Temperature": ("Température", "°C", 35.5, 38.5, "inhabituelle"),
    "FrequenceRespiratoire": ("Respiration", "/min", 10, 24, "inhabituelle"),
}

# Bornes « lit » : valeurs plausibles pour un monitoring d’étage
BEDSIDE_RANGES: dict[str, tuple[float, float]] = {
    "FrequenceCardiaque": (48.0, 128.0),
    "TensionSystolique": (95.0, 175.0),
    "TensionDiastolique": (55.0, 105.0),
    "Temperature": (35.8, 39.0),
    "FrequenceRespiratoire": (11.0, 28.0),
    "SpO2": (88.0, 100.0),
}

DEFAULT_BASELINE: dict[str, float] = {
    "FrequenceCardiaque": 78.0,
    "TensionSystolique": 128.0,
    "TensionDiastolique": 78.0,
    "Temperature": 36.8,
    "FrequenceRespiratoire": 16.0,
    "SpO2": 97.0,
}

# Une « époque clinique » ≈ 90 s : assez lent pour qu’un soignant suive
TICK_SECONDS = 5
EPOCH_TICKS = 18  # 18 × 5 s ≈ 90 s entre évolutions notables
VITAL_COLS = tuple(DEFAULT_BASELINE.keys())


# Nombre de chambres physiques par service (démo) — 6 × 2 lits = 12 lits max
N_CHAMBRES_PAR_SERVICE = 6
LITS_PAR_CHAMBRE = ("A", "B")
MAX_LITS_PAR_SERVICE = N_CHAMBRES_PAR_SERVICE * len(LITS_PAR_CHAMBRE)
MAX_URGENT_PAR_SERVICE = 2

# Rythme pédagogique des urgences (compréhensible en démo)
URGENCE_CYCLE_SEC = 180  # cycle de 3 minutes
URGENCE_ACTIVE_SEC = 120  # 2 min d’alerte, puis 1 min sans urgence


def fenetre_urgence_pedagogique(now: float | None = None) -> tuple[int, bool, int]:
    """
    Cycle démo :
    - minutes 0–2 : une urgence active par étage
    - minute 2–3 : calme (aucune urgence machine)
    Retourne (n°cycle, alerte_active, secondes_restantes_dans_la_phase).
    """
    t = time.time() if now is None else float(now)
    cycle = int(t // URGENCE_CYCLE_SEC)
    pos = t % URGENCE_CYCLE_SEC
    active = pos < URGENCE_ACTIVE_SEC
    restant = int((URGENCE_ACTIVE_SEC if active else URGENCE_CYCLE_SEC) - pos)
    return cycle, active, max(0, restant)


def appliquer_urgence_pedagogique(
    rooms: list[dict[str, Any]],
    *,
    etage_libelle: str,
    cycle: int,
    active: bool,
) -> list[dict[str, Any]]:
    """
    Force au plus 1 urgence claire par étage, qui change à chaque cycle de 3 min.
    Évite les alertes « aléatoires » peu pédagogiques.
    """
    out: list[dict[str, Any]] = []
    for r in rooms:
        rr = dict(r)
        if rr.get("vide") or rr.get("niveau") in {"disponible", "a_nettoyer"}:
            out.append(rr)
            continue
        # Retire d’abord les urgences « naturelles » (fragilité continue)
        if rr.get("niveau") == "urgent":
            proba = rr.get("proba") or 0
            rr["niveau"] = "a_surveiller" if proba >= 0.50 else "calme"
            rr["alertes"] = []
            if rr.get("constantes") and rr["constantes"].get("SpO2", 100) < 92:
                rr["constantes"] = dict(rr["constantes"])
                rr["constantes"]["SpO2"] = 94
            rr["consigne"] = (
                f"Chambre {rr['chambre']} : constantes sous surveillance, "
                "pas d’alerte prioritaire pour le moment."
            )
            rr["score_news"] = score_news_simplifie(rr.get("constantes") or {})
        out.append(rr)

    if not active:
        return out

    candidats = [
        r
        for r in out
        if not r.get("vide")
        and r.get("SejourID")
        and r.get("niveau") not in {"disponible", "a_nettoyer"}
        and service_est_monitoring_continu(r.get("service_code"))
    ]
    if not candidats:
        return out

    h = int(
        hashlib.sha256(f"{etage_libelle}|cycle|{cycle}".encode()).hexdigest(), 16
    )
    choisi = candidats[h % len(candidats)]
    for i, r in enumerate(out):
        if r.get("SejourID") != choisi.get("SejourID"):
            continue
        vitals = dict(r.get("constantes") or {})
        vitals["SpO2"] = 89
        vitals["FrequenceRespiratoire"] = max(
            int(vitals.get("FrequenceRespiratoire") or 16), 22
        )
        alerts = alertes_machines(vitals)
        out[i] = {
            **r,
            "niveau": "urgent",
            "constantes": vitals,
            "alertes": alerts,
            "score_news": score_news_simplifie(vitals),
            "consigne": message_soignant(
                chambre=str(r["chambre"]),
                vitals=vitals,
                machine_alerts=alerts,
                risque_sortie=False,
                document="",
            ),
            "urgence_pedagogique": True,
        }
        break
    return out


def sejour_est_urgence_pedagogique(
    sejour_id: str,
    candidats_ids: list[str],
    *,
    etage_libelle: str,
    now: float | None = None,
) -> tuple[bool, int]:
    """True si ce séjour est la cible d’urgence pédagogique du cycle (même règle que le board)."""
    cycle, active, restant = fenetre_urgence_pedagogique(now)
    if not active or not candidats_ids:
        return False, restant
    # Pas d’urgence machine pédagogique hors monitoring continu
    return str(sejour_id) == str(
        candidats_ids[
            int(hashlib.sha256(f"{etage_libelle}|cycle|{cycle}".encode()).hexdigest(), 16)
            % len(candidats_ids)
        ]
    ), restant


def appliquer_vitals_urgence_pedagogique(vitals: dict[str, Any]) -> dict[str, Any]:
    """Même forçage SpO2/FR que le plan d’étage (toast ALERT)."""
    out = dict(vitals or {})
    out["SpO2"] = 89
    out["FrequenceRespiratoire"] = max(int(out.get("FrequenceRespiratoire") or 16), 22)
    return out


def statut_constantes_alerte(vitals: dict[str, Any]) -> dict[str, bool]:
    """Par constante : True si hors seuil soignant (ALERT_RULES)."""
    flags: dict[str, bool] = {}
    for key, (_label, _unit, low, high, _adj) in ALERT_RULES.items():
        val = vitals.get(key)
        if val is None:
            flags[key] = False
            continue
        flags[key] = (low is not None and val < low) or (high is not None and val > high)
    return flags


_CHART_SERIES = (
    ("SpO2", "Oxygène (SpO₂)", "%", 92.0),
    ("FrequenceCardiaque", "Pouls", "/min", None),
    ("FrequenceRespiratoire", "Respiration", "/min", None),
    ("Temperature", "Température", "°C", None),
    ("TensionSystolique", "Tension systolique", "mmHg", None),
    ("PoidsKg", "Poids", "kg", None),
)

# Fenêtre moniteur interactif : 1 point / tick (5 s) → ~4 min visibles
MONITEUR_N_POINTS = 48
MONITEUR_STEP_TICKS = 1
MONITEUR_REFRESH_SEC = TICK_SECONDS


def _label_temps_relatif(seconds_ago: int) -> str:
    if seconds_ago <= 0:
        return "maintenant"
    m, s = divmod(max(0, int(seconds_ago)), 60)
    if m == 0:
        return f"−{s}s"
    return f"−{m}:{s:02d}"


def series_evolution_live(
    profil: dict[str, Any] | None,
    *,
    tick: int,
    n_points: int = MONITEUR_N_POINTS,
    step_ticks: int = MONITEUR_STEP_TICKS,
    vitals_override: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Séries moniteur pour graphiques interactifs (Chart.js).

    Un point toutes les ``step_ticks`` (défaut 5 s) — la courbe bouge à chaque
    rafraîchissement de la fiche.
    """
    if not profil:
        return []
    t = int(tick)
    step = max(1, int(step_ticks))
    labels: list[str] = []
    series: dict[str, list[float]] = {k: [] for k, *_ in _CHART_SERIES}
    for i in range(n_points - 1, -1, -1):
        sample_tick = max(0, t - i * step)
        seconds_ago = (t - sample_tick) * TICK_SECONDS
        labels.append(_label_temps_relatif(seconds_ago))
        snap = snapshot_constantes(profil, tick=sample_tick)
        if i == 0 and vitals_override:
            snap = {**snap, **vitals_override}
        for key, *_ in _CHART_SERIES:
            v = snap.get(key)
            if v is not None:
                series[key].append(float(v))
            else:
                series[key].append(None)

    charts: list[dict[str, Any]] = []
    for key, label, unit, seuil in _CHART_SERIES:
        vals = series.get(key) or []
        clean = [v for v in vals if v is not None]
        if len(clean) < 2:
            continue
        charts.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "seuil": seuil,
                "labels": labels,
                "values": vals,
                "n": len(clean),
                "dernier": clean[-1],
                "min": min(clean),
                "max": max(clean),
            }
        )
    return charts


def series_evolution_from_historique(
    historique: dict[str, Any] | None,
    *,
    max_points: int = 40,
) -> list[dict[str, Any]]:
    """Séries chronologiques (mesures retenues du dossier) — format interactif."""
    if not historique:
        return []
    mesures = list(historique.get("mesures_retenues") or historique.get("mesures") or [])
    mesures = [m for m in mesures if not m.get("exclue")]
    mesures = list(reversed(mesures))
    if len(mesures) > max_points:
        step = max(1, len(mesures) // max_points)
        mesures = mesures[::step][-max_points:]
    if len(mesures) < 2:
        return []

    labels = []
    for i, m in enumerate(mesures):
        t = str(m.get("Horodatage") or "")
        labels.append(t[11:16] if len(t) >= 16 else (t or f"#{i + 1}"))

    charts: list[dict[str, Any]] = []
    for key, label, unit, seuil in _CHART_SERIES:
        vals: list[float | None] = []
        for m in mesures:
            v = m.get(key)
            vals.append(float(v) if v is not None else None)
        clean = [v for v in vals if v is not None]
        if len(clean) < 2:
            continue
        charts.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "seuil": seuil,
                "labels": labels,
                "values": vals,
                "n": len(clean),
                "dernier": clean[-1],
                "min": min(clean),
                "max": max(clean),
            }
        )
    return charts


def _chambre_numero(etage: int, room_index: int) -> str:
    if etage == 0:
        return f"R{room_index:02d}"
    return f"{etage}{room_index:02d}"


def services_du_plan() -> list[str]:
    out: list[str] = []
    for floor in FLOOR_PLAN:
        for svc in floor["services"]:
            if svc not in out:
                out.append(svc)
    return out


def sejours_pour_service(service: str, sejour_ids: list[str]) -> list[str]:
    """Répartit la cohorte CSV entre services réels et unités virtuelles."""
    source = SERVICE_DATA_SOURCE.get(service, service)
    cohorte = list(sejour_ids)
    if service == source:
        return cohorte
    siblings = sorted(
        svc
        for floor in FLOOR_PLAN
        for svc in floor["services"]
        if SERVICE_DATA_SOURCE.get(svc, svc) == source
    )
    if service not in siblings:
        return cohorte
    bucket = siblings.index(service)
    n = len(siblings)
    out: list[str] = []
    for sej in cohorte:
        h = int(hashlib.sha256(f"{source}|virt|{sej}".encode()).hexdigest(), 16)
        if h % n == bucket:
            out.append(sej)
    if not out and cohorte:
        out = cohorte[bucket::n]
    return out


def localisation_pour(sejour_id: str, service: str) -> dict[str, Any]:
    """Chambre, lit et étage stables pour la démo (hors CSV du sujet)."""
    meta = UNITE_PAR_SERVICE.get(
        service,
        {"etage": 3, "aile": "Aile E", "uf": "UF-MED", "poste": "Médecine", "chambre_offset": 0},
    )
    h = int(hashlib.sha256(f"{service}|{sejour_id}".encode()).hexdigest(), 16)
    num_local = 1 + (h % N_CHAMBRES_PAR_SERVICE)
    offset = int(meta.get("chambre_offset", 0))
    room_index = offset + num_local
    etage = int(meta["etage"])
    chambre = _chambre_numero(etage, room_index)
    lit = "A" if ((h // N_CHAMBRES_PAR_SERVICE) % 2 == 0) else "B"
    etage_libelle = "RDC" if etage == 0 else f"{etage}e étage"
    equipe = EQUIPE_PAR_SERVICE.get(service, {})
    ide = libelle_personne(equipe.get("infirmier"))
    aso = libelle_personne(equipe.get("aide_soignante"))
    return {
        "etage": etage,
        "etage_libelle": etage_libelle,
        "chambre": chambre,
        "lit": lit,
        "lit_complet": f"{chambre}{lit}",
        "aile": meta["aile"],
        "uf": meta["uf"],
        "poste": meta["poste"],
        "ide_equipe": f"IDE {ide}" if ide != "—" else f"IDE {meta['aile']}",
        "as_equipe": f"AS {aso}" if aso != "—" else "AS —",
    }


def slots_lits_service(service: str) -> list[dict[str, Any]]:
    """Tous les lits physiques d’un service (occupés ou libres)."""
    meta = UNITE_PAR_SERVICE.get(
        service,
        {"etage": 3, "aile": "Aile E", "uf": "UF-MED", "poste": "Médecine", "chambre_offset": 0},
    )
    etage = int(meta["etage"])
    etage_libelle = "RDC" if etage == 0 else f"{etage}e étage"
    offset = int(meta.get("chambre_offset", 0))
    slots = []
    for num in range(1, N_CHAMBRES_PAR_SERVICE + 1):
        room_index = offset + num
        chambre = _chambre_numero(etage, room_index)
        for lit in LITS_PAR_CHAMBRE:
            slots.append(
                {
                    "etage": etage,
                    "etage_libelle": etage_libelle,
                    "chambre": chambre,
                    "lit": lit,
                    "lit_complet": f"{chambre}{lit}",
                    "aile": meta["aile"],
                    "uf": meta["uf"],
                    "poste": meta["poste"],
                    "service": SERVICE_LABELS.get(service, service),
                    "service_code": service,
                }
            )
    return slots


def chambre_pour(sejour_id: str, service: str) -> str:
    return str(localisation_pour(sejour_id, service)["chambre"])


def score_news_simplifie(vitals: dict[str, Any]) -> int | None:
    """Score d’alerte type NEWS (barème simplifié, pédagogique)."""
    if not vitals:
        return None
    score = 0
    spo2 = vitals.get("SpO2")
    if spo2 is not None:
        if spo2 <= 91:
            score += 3
        elif spo2 <= 93:
            score += 2
        elif spo2 <= 95:
            score += 1
    hr = vitals.get("FrequenceCardiaque")
    if hr is not None:
        if hr <= 40 or hr >= 131:
            score += 3
        elif hr >= 111 or hr <= 50:
            score += 2
        elif hr >= 91:
            score += 1
    sys_ = vitals.get("TensionSystolique")
    if sys_ is not None:
        if sys_ <= 90 or sys_ >= 220:
            score += 3
        elif sys_ <= 100:
            score += 2
        elif sys_ <= 110:
            score += 1
    temp = vitals.get("Temperature")
    if temp is not None:
        if temp <= 35.0 or temp >= 39.1:
            score += 3
        elif temp >= 38.1 or temp <= 35.9:
            score += 1
    rr = vitals.get("FrequenceRespiratoire")
    if rr is not None:
        if rr <= 8 or rr >= 25:
            score += 3
        elif rr >= 21:
            score += 2
        elif rr <= 11:
            score += 1
    return score


def _clip(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def _est_valide_lit(col: str, val: float) -> bool:
    low, high = BEDSIDE_RANGES[col]
    return low <= val <= high


def _rng(seed: str) -> float:
    """Pseudo-aléatoire déterministe dans [0, 1)."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _signed_unit(seed: str) -> float:
    return _rng(seed) * 2.0 - 1.0


def _baseline_depuis_mesures(rows: list[dict[str, Any]], sejour_id: str) -> dict[str, Any]:
    """Médiane des mesures plausibles ; ignore les aberrations du CSV pédagogique."""
    base = dict(DEFAULT_BASELINE)
    for col in VITAL_COLS:
        vals = [
            float(r[col])
            for r in rows
            if r.get(col) is not None and _est_valide_lit(col, float(r[col]))
        ]
        if vals:
            vals.sort()
            base[col] = vals[len(vals) // 2]

    # Cohérence tension : pression pulsée 30–60 mmHg
    tas = base["TensionSystolique"]
    tad = base["TensionDiastolique"]
    if tad >= tas - 25:
        tad = tas - 40.0
    if tas - tad > 70:
        tad = tas - 50.0
    base["TensionDiastolique"] = _clip(tad, *BEDSIDE_RANGES["TensionDiastolique"])
    base["TensionSystolique"] = _clip(tas, *BEDSIDE_RANGES["TensionSystolique"])

    # Profil clinique stable du patient (ne change pas pendant la démo)
    h = int(hashlib.sha256(sejour_id.encode()).hexdigest(), 16)
    # ~8 % des lits : un peu plus fragiles, sans déclencher d’urgence seule
    # (les urgences sont pilotées par le rythme pédagogique 3 min)
    fragilite = (h % 100) < 8
    return {
        "sejour_id": sejour_id,
        "baseline": base,
        "fragilite": fragilite,
        "phase0": (h % 360) / 57.3,  # décalage de phase (radians approx.)
    }


def index_constantes(signes: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Construit un profil stable par séjour (plus de rejeu brut du CSV)."""
    sv = signes.copy()
    sv["Horodatage"] = pd.to_datetime(sv["Horodatage"], errors="coerce")
    sv = sv.dropna(subset=["SejourID", "Horodatage"]).sort_values("Horodatage")
    out: dict[str, dict[str, Any]] = {}
    for sej, grp in sv.groupby("SejourID"):
        rows = []
        for rec in grp[list(VITAL_COLS)].to_dict(orient="records"):
            rows.append(
                {k: (None if pd.isna(v) else float(v)) for k, v in rec.items()}
            )
        if rows:
            out[str(sej)] = _baseline_depuis_mesures(rows, str(sej))
    return out


def _derive_vitals(profil: dict[str, Any], *, epoch: int, tick: int) -> dict[str, Any]:
    """
    Évolution lente et physiologiquement cohérente.

    - Époque (~90 s) : petite dérive clinique (quelques unités max).
    - Tick (5 s) : micro-variation du pouls seulement (±1), comme un moniteur réel.
    """
    sej = str(profil["sejour_id"])
    base = profil["baseline"]
    frag = bool(profil["fragilite"])
    phase = float(profil["phase0"])

    # Dérive lente sinusoïdale + offset d’époque (déterministe)
    wave = math.sin(phase + epoch * 0.35)
    drift_seed = f"{sej}|epoch|{epoch}"

    # Amplitudes réalistes sur ~90 s (pas de sauts de 30 bpm)
    d_hr = 3.0 * wave + 1.5 * _signed_unit(drift_seed + "|hr")
    d_spo2 = 0.6 * wave + 0.4 * _signed_unit(drift_seed + "|spo2")
    d_temp = 0.08 * wave + 0.04 * _signed_unit(drift_seed + "|temp")
    d_tas = 4.0 * wave + 2.0 * _signed_unit(drift_seed + "|tas")
    d_rr = 1.2 * wave + 0.6 * _signed_unit(drift_seed + "|rr")

    if frag:
        # Fragilité légère (toujours SpO2 ≥ 93) — l’urgence franche est calendaire
        d_spo2 -= 2.0 + 0.5 * abs(wave)
        d_rr += 1.2 + 0.5 * abs(wave)
        d_hr += 3.0 * abs(wave)

    hr = base["FrequenceCardiaque"] + d_hr
    # Micro-jitter moniteur (1 bpm max), jamais un nouveau « scénario »
    hr += 0.8 * _signed_unit(f"{sej}|tick|{tick}|micro")

    spo2 = base["SpO2"] + d_spo2
    if frag:
        # Garde-fou : la fragilité ne déclenche plus seule une urgence SpO2
        spo2 = max(spo2, 93.0)
    temp = base["Temperature"] + d_temp
    tas = base["TensionSystolique"] + d_tas
    # Diastole suit la systole (pression pulsée ~40 mmHg ± lente)
    pulse = 40.0 + 3.0 * _signed_unit(drift_seed + "|pp")
    tad = tas - pulse
    # Respiration : suit un peu le pouls (stress / hypoxie)
    rr = base["FrequenceRespiratoire"] + d_rr + 0.04 * (hr - base["FrequenceCardiaque"])

    vitals = {
        "FrequenceCardiaque": round(_clip(hr, *BEDSIDE_RANGES["FrequenceCardiaque"])),
        "SpO2": round(_clip(spo2, *BEDSIDE_RANGES["SpO2"])),
        "Temperature": round(_clip(temp, *BEDSIDE_RANGES["Temperature"]), 1),
        "TensionSystolique": round(_clip(tas, *BEDSIDE_RANGES["TensionSystolique"])),
        "TensionDiastolique": round(
            _clip(tad, *BEDSIDE_RANGES["TensionDiastolique"])
        ),
        "FrequenceRespiratoire": round(
            _clip(rr, *BEDSIDE_RANGES["FrequenceRespiratoire"])
        ),
    }
    # Garantie finale TAS > TAD + 20
    if vitals["TensionDiastolique"] >= vitals["TensionSystolique"] - 20:
        vitals["TensionDiastolique"] = max(
            int(BEDSIDE_RANGES["TensionDiastolique"][0]),
            vitals["TensionSystolique"] - 40,
        )
    return vitals


def current_tick() -> int:
    return int(time.time() // TICK_SECONDS)


def snapshot_constantes(
    profil: dict[str, Any] | list | None,
    *,
    tick: int | None = None,
) -> dict[str, Any]:
    """Instantané monitoring : lent, cohérent, sans rejeu des aberrations CSV."""
    if not profil:
        return {}
    # Compat : ancienne forme (liste de lignes brutes)
    if isinstance(profil, list):
        if not profil:
            return {}
        sej = "LEGACY"
        profil = _baseline_depuis_mesures(profil, sej)
    t = current_tick() if tick is None else int(tick)
    epoch = t // EPOCH_TICKS
    return _derive_vitals(profil, epoch=epoch, tick=t)


def tendance_constantes(profil: dict[str, Any] | None, *, tick: int | None = None) -> str:
    """Libellé soignant : évolution lisible, pas un flash."""
    if not profil:
        return "sans capteur"
    t = current_tick() if tick is None else int(tick)
    now = snapshot_constantes(profil, tick=t)
    prev = snapshot_constantes(profil, tick=max(0, t - EPOCH_TICKS))
    if not now or not prev:
        return "stable"
    d_spo2 = (now.get("SpO2") or 0) - (prev.get("SpO2") or 0)
    d_hr = (now.get("FrequenceCardiaque") or 0) - (prev.get("FrequenceCardiaque") or 0)
    if d_spo2 <= -2 or d_hr >= 8:
        return "en baisse"
    if d_spo2 >= 2 or d_hr <= -8:
        return "en amélioration"
    return "stable"


def alertes_machines(vitals: dict[str, Any]) -> list[dict[str, str]]:
    alerts = []
    for key, (label, unit, low, high, adj) in ALERT_RULES.items():
        val = vitals.get(key)
        if val is None:
            continue
        bad = (low is not None and val < low) or (high is not None and val > high)
        if bad:
            alerts.append(
                {
                    "code": key,
                    "niveau": "urgent",
                    "titre": f"{label} {adj}",
                    "detail": f"{label} mesurée à {val:.0f} {unit}."
                    if key != "Temperature"
                    else f"{label} mesurée à {val:.1f} {unit}.",
                    "action": "Passer dans la chambre et prévenir le médecin si besoin.",
                }
            )
    return alerts


def message_soignant(
    *,
    chambre: str,
    vitals: dict[str, Any],
    machine_alerts: list[dict[str, str]],
    risque_sortie: bool,
    document: str,
) -> str:
    """Texte immédiat (sans LLM) : clair pour infirmier / médecin."""
    if machine_alerts:
        a = machine_alerts[0]
        return (
            f"Chambre {chambre} : {a['titre']}. {a['detail']} "
            f"{a['action']}"
        )
    if risque_sortie:
        extra = ""
        if document:
            extra = " Le dossier évoque un suivi à prévoir après la sortie."
        return (
            f"Chambre {chambre} : pas d’alerte machine en ce moment, "
            f"mais le risque de revenir à l’hôpital dans les 30 jours est élevé.{extra} "
            "Prévoir un appel ou une visite à domicile."
        )
    spo2 = vitals.get("SpO2")
    if spo2 is not None:
        return (
            f"Chambre {chambre} : constantes stables pour l’instant "
            f"(saturation {spo2:.0f} %). Continuer la surveillance habituelle."
        )
    return f"Chambre {chambre} : surveillance en cours, aucune alerte machine."


def generate_brief_llm(llm, chambre: str, vitals: dict[str, Any], document: str) -> str:
    from src.nlp.guardrails import hallucination_rate

    vit = ", ".join(
        f"{k}={v:.1f}" for k, v in vitals.items() if v is not None
    )
    prompt = (
        "<|im_start|>system\nTu parles à une infirmière, en français simple, "
        "sans jargon informatique. 1 phrase. N'invente aucun chiffre hors de la liste.<|im_end|>\n"
        f"<|im_start|>user\nChambre {chambre}. Constantes: {vit}. "
        f"Notes: {document[:280]}\nDis si on doit passer voir le patient maintenant.<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    out = llm(prompt, max_tokens=60, temperature=0.0, stop=["<|im_end|>", "<|im_start|>"])
    text = out["choices"][0]["text"].strip()
    src = vit + " " + document
    if not text or hallucination_rate(src, text) > 0.35:
        return ""
    return text
