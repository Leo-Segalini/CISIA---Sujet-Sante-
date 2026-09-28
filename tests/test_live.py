from src.web.affichage import nom_famille
from src.web.live import (
    EPOCH_TICKS,
    BEDSIDE_RANGES,
    alertes_machines,
    appliquer_vitals_urgence_pedagogique,
    chambre_pour,
    localisation_pour,
    series_evolution_from_historique,
    snapshot_constantes,
    service_est_monitoring_continu,
    statut_constantes_alerte,
)
from src.web.services import live_board, predict_sejour, saisir_constantes_sejour


def test_chambre_stable():
    a = chambre_pour("SEJ-000001", "Cardiologie")
    b = chambre_pour("SEJ-000001", "Cardiologie")
    assert a == b
    loc = localisation_pour("SEJ-000001", "Cardiologie")
    assert loc["etage"] == 2
    assert loc["lit"] in {"A", "B"}
    assert a == loc["chambre"]


def test_monitoring_continu_par_service():
    assert service_est_monitoring_continu("SoinsContinus") is True
    assert service_est_monitoring_continu("Chirurgie") is False
    assert service_est_monitoring_continu("MedecineInterne") is False
    assert service_est_monitoring_continu("Cardiologie") is False


def test_saisie_manuelle_refuse_soins_continus():
    board = live_board(max_par_service=8)
    sej_continu = None
    sej_manuel = None
    for rooms in board["etages"].values():
        for r in rooms:
            if r.get("vide") or not r.get("SejourID"):
                continue
            if r.get("monitoring_continu") and sej_continu is None:
                sej_continu = r["SejourID"]
            if (not r.get("monitoring_continu")) and sej_manuel is None:
                sej_manuel = r["SejourID"]
    if sej_continu:
        try:
            saisir_constantes_sejour(
                sej_continu,
                {"FrequenceCardiaque": 80, "SpO2": 97},
            )
            assert False, "attendu ValueError"
        except ValueError:
            pass
    if sej_manuel:
        out = saisir_constantes_sejour(
            sej_manuel,
            {
                "FrequenceCardiaque": 76,
                "SpO2": 96,
                "Temperature": 36.9,
                "PoidsKg": 71.5,
                "Horodatage": "2026-09-28 10:00",
            },
        )
        assert out["monitoring_continu"] is False
        assert out["constantes"]["SpO2"] == 96
        assert out["constantes"]["PoidsKg"] == 71.5
        d = predict_sejour(sej_manuel)
        assert d["monitoring_continu"] is False
        assert d["constantes"]["SpO2"] == 96
        assert d["PoidsKg"] == 71.5


def test_alerte_spo2_basse():
    alerts = alertes_machines({"SpO2": 88.0, "FrequenceCardiaque": 80.0})
    assert any(x["code"] == "SpO2" for x in alerts)


def test_vitals_urgence_pedagogique_alignee_toast():
    """Fiche patient : mêmes SpO2/FR que le toast ALERT du plan d’étage."""
    base = {
        "FrequenceCardiaque": 78.0,
        "SpO2": 97.0,
        "FrequenceRespiratoire": 16.0,
        "Temperature": 36.8,
        "TensionSystolique": 128.0,
        "TensionDiastolique": 78.0,
    }
    forced = appliquer_vitals_urgence_pedagogique(base)
    assert forced["SpO2"] == 89
    assert forced["FrequenceRespiratoire"] >= 22
    flags = statut_constantes_alerte(forced)
    assert flags["SpO2"] is True
    assert any(a["code"] == "SpO2" for a in alertes_machines(forced))


def test_series_evolution_sparkline():
    hist = {
        "mesures_retenues": [
            {"Horodatage": f"2024-01-01T10:{i:02d}:00", "SpO2": 98.0 - i * 0.5, "FrequenceCardiaque": 70 + i}
            for i in range(5)
        ]
    }
    charts = series_evolution_from_historique(hist)
    spo2 = next(c for c in charts if c["key"] == "SpO2")
    assert spo2["n"] == 5
    assert len(spo2["values"]) == 5
    assert len(spo2["labels"]) == 5
    assert spo2["seuil"] == 92


def test_series_evolution_live_visible():
    from src.web.live import series_evolution_live

    profil = {
        "sejour_id": "SEJ-TEST",
        "baseline": {
            "FrequenceCardiaque": 80.0,
            "TensionSystolique": 130.0,
            "TensionDiastolique": 80.0,
            "Temperature": 36.8,
            "FrequenceRespiratoire": 16.0,
            "SpO2": 97.0,
        },
        "fragilite": False,
        "phase0": 0.5,
    }
    charts = series_evolution_live(profil, tick=200, vitals_override={"SpO2": 89})
    assert len(charts) >= 4
    spo2 = next(c for c in charts if c["key"] == "SpO2")
    assert spo2["n"] >= 10
    assert spo2["dernier"] == 89
    assert spo2["labels"][-1] == "maintenant"
    assert len(spo2["values"]) == len(spo2["labels"])


def test_vitals_lents_et_coherents():
    profil = {
        "sejour_id": "SEJ-TEST",
        "baseline": {
            "FrequenceCardiaque": 80.0,
            "TensionSystolique": 130.0,
            "TensionDiastolique": 80.0,
            "Temperature": 36.8,
            "FrequenceRespiratoire": 16.0,
            "SpO2": 97.0,
        },
        "fragilite": False,
        "phase0": 0.5,
    }
    a = snapshot_constantes(profil, tick=100)
    b = snapshot_constantes(profil, tick=101)
    # Même époque : pouls ne saute presque pas
    assert abs(a["FrequenceCardiaque"] - b["FrequenceCardiaque"]) <= 2
    assert abs(a["SpO2"] - b["SpO2"]) <= 1
    assert a["TensionDiastolique"] < a["TensionSystolique"] - 20
    # Époque suivante : dérive limitée (suivable par un soignant)
    c = snapshot_constantes(profil, tick=100 + EPOCH_TICKS)
    assert abs(c["FrequenceCardiaque"] - a["FrequenceCardiaque"]) <= 12
    assert abs(c["SpO2"] - a["SpO2"]) <= 3
    assert abs(c["Temperature"] - a["Temperature"]) <= 0.4
    for col, (low, high) in BEDSIDE_RANGES.items():
        assert low <= a[col] <= high


def test_live_board_has_rooms():
    board = live_board(max_par_service=2)
    assert board["etages"]
    first_etage = next(iter(board["etages"].values()))
    assert first_etage
    occupe = next(r for r in first_etage if not r.get("vide"))
    assert "chambre" in occupe
    assert "NomFamille" in occupe
    assert "Sexe" in occupe
    assert "tendance" in occupe
    assert occupe["niveau"] in {"urgent", "a_surveiller", "calme"}
    c = occupe["constantes"]
    assert c.get("FrequenceCardiaque", 0) >= 48
    assert c.get("SpO2", 0) >= 88


def test_live_board_mix_niveaux():
    """L’étage ne doit pas être rempli uniquement de cas « à surveiller »."""
    board = live_board(max_par_service=8)
    niveaux = [
        r["niveau"]
        for rooms in board["etages"].values()
        for r in rooms
        if not r.get("vide")
    ]
    assert niveaux
    assert "calme" in niveaux
    assert niveaux.count("a_surveiller") < len(niveaux)


def test_urgence_pedagogique_une_par_etage_et_lits_vides():
    """Au plus 1 urgence claire par étage (phase alerte), 0 en phase calme."""
    from src.web.live import fenetre_urgence_pedagogique

    board = live_board(max_par_service=8)
    _, active, _ = fenetre_urgence_pedagogique()
    for etage, rooms in board["etages"].items():
        n_u = sum(1 for r in rooms if r["niveau"] == "urgent" and not r.get("vide"))
        if active:
            assert n_u <= 1, f"{etage} a {n_u} urgents (attendu ≤ 1)"
        else:
            assert n_u == 0, f"{etage} a {n_u} urgents en phase calme"
        assert any(r.get("vide") or r["niveau"] in {"disponible", "a_nettoyer"} for r in rooms)
    assert "rythme_pedagogique" in board
    assert board["urgence_active"] is active
    if active:
        assert board["n_urgent"] <= len(board["etages"])
    else:
        assert board["n_urgent"] == 0


def test_fenetre_urgence_cycle_3_min():
    from src.web.live import URGENCE_ACTIVE_SEC, URGENCE_CYCLE_SEC, fenetre_urgence_pedagogique

    # Début de cycle → alerte
    c0, a0, r0 = fenetre_urgence_pedagogique(now=0.0)
    assert c0 == 0 and a0 is True and r0 == URGENCE_ACTIVE_SEC
    # Fin de phase alerte → calme
    c1, a1, _ = fenetre_urgence_pedagogique(now=float(URGENCE_ACTIVE_SEC + 1))
    assert c1 == 0 and a1 is False
    # Cycle suivant
    c2, a2, _ = fenetre_urgence_pedagogique(now=float(URGENCE_CYCLE_SEC))
    assert c2 == 1 and a2 is True


def test_nettoyer_deces_et_admettre():
    from src.web.services import admettre_lit, get_store, nettoyer_lit

    get_store.cache_clear()
    board = live_board(max_par_service=8)
    a_nettoyer = next(
        r
        for rooms in board["etages"].values()
        for r in rooms
        if r["niveau"] == "a_nettoyer"
    )
    out = nettoyer_lit(
        service=a_nettoyer["service_code"],
        chambre=a_nettoyer["chambre"],
        lit=a_nettoyer["lit"],
    )
    assert out["etat"] == "disponible"
    board2 = live_board(max_par_service=8)
    dispo = next(
        r
        for rooms in board2["etages"].values()
        for r in rooms
        if r["chambre"] == a_nettoyer["chambre"]
        and r["lit"] == a_nettoyer["lit"]
        and r["niveau"] == "disponible"
    )
    adm = admettre_lit(
        service=dispo["service_code"],
        chambre=dispo["chambre"],
        lit=dispo["lit"],
    )
    assert adm["SejourID"]
    board3 = live_board(max_par_service=8)
    occ = next(
        r
        for rooms in board3["etages"].values()
        for r in rooms
        if r["chambre"] == dispo["chambre"]
        and r["lit"] == dispo["lit"]
        and not r.get("vide")
    )
    assert occ["SejourID"] == adm["SejourID"]


def test_predict_has_plain_consigne():
    from src.web.services import list_sejours

    sej = list_sejours(page_size=1)["items"][0]["SejourID"]
    d = predict_sejour(sej)
    assert "chambre" in d
    assert "lit" in d
    assert "etage_libelle" in d
    assert "consigne" in d
    assert "NomFamille" in d
    assert "NomPrenom" not in d
    assert "PersonneAPrevenir" not in d
    assert d["NomFamille"] == d["NomFamille"].upper()
    assert d.get("tendance_constantes") in {
        "stable",
        "en baisse",
        "en amélioration",
        "sans capteur",
    }


def test_nom_famille_only():
    assert nom_famille("Martin Monique") == "MARTIN"
    assert nom_famille("") == "—"
