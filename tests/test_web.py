from src.web.services import (
    biais_rows,
    list_sejours,
    list_sejours_cisia,
    overview,
    predict_sejour,
    registre_rows,
)


def test_overview_has_counts():
    ov = overview()
    assert ov["n_sejours"] > 0
    assert ov["bind"] == "127.0.0.1"
    assert "modele_retenu" in ov


def test_list_and_predict_first_sejour():
    data = list_sejours(page=1, page_size=5)
    assert data["total"] > 0
    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "NomFamille" in item
    assert "Prenom" in item
    assert item["Prenom"] != ""
    assert "chambre" in item
    assert "lit_complet" in item
    assert "etage" in item
    assert "filters" in data
    sej = item["SejourID"]
    detail = predict_sejour(sej)
    assert detail["SejourID"] == sej
    assert "NomPrenom" not in detail
    assert detail["NomFamille"]
    assert 0 <= detail["proba_readmission_30j"] <= 1
    assert "proba_pct" in detail
    assert "justification" in detail
    assert "explication_risque_30j" in detail
    assert detail["explication_risque_30j"]
    assert "facteurs_risque_patient" in detail
    assert "constantes_historique" in detail
    hist = detail["constantes_historique"]
    assert hist["total"] >= 0
    assert "mesures" in hist
    assert "territoire" in detail
    if detail["top_shap_global"]:
        assert "libelle" in detail["top_shap_global"][0]
        assert "valeur" in detail["top_shap_global"][0]
        assert "bar_pct" in detail["top_shap_global"][0]


def test_list_sejours_filters():
    all_data = list_sejours(page_size=500)
    assert all_data["total"] > 0

    by_etage = list_sejours(etage=1, page_size=500)
    assert by_etage["total"] > 0
    assert all(row["etage"] == 1 for row in by_etage["items"])

    by_service = list_sejours(service="Cardiologie", page_size=500)
    assert by_service["total"] > 0
    assert all(row["Service"] == "Cardiologie" for row in by_service["items"])

    by_sexe = list_sejours(sexe="F", page_size=500)
    assert by_sexe["total"] > 0
    assert all(row["Sexe"] == "F" for row in by_sexe["items"])

    sample = all_data["items"][0]
    by_q = list_sejours(q=sample["NomFamille"][:3], page_size=500)
    assert by_q["total"] >= 1


def test_registre_non_empty():
    rows = registre_rows()
    assert len(rows) >= 50
    assert "sensibilite" in rows[0]
    assert "origine_donnee" in rows[0]
    origines = {r["origine_donnee"] for r in rows}
    assert "sujet" in origines
    assert "insee_ajoute" in origines


def test_registre_report_structure():
    from src.web.services import registre_report

    report = registre_report()
    assert report["total_all"] >= 50
    assert len(report["file_groups"]) >= 5
    assert report["file_groups"][0]["rows"][0]["origine_label"]
    filtered = registre_report(origine="insee_ajoute")
    assert filtered["total_filtered"] == report["stats"]["insee"]


def test_biais_rows_sortie():
    rows = biais_rows(score="sortie")
    assert len(rows) >= 3
    assert "groupe" in rows[0]
    assert "rappel" in rows[0]
    assert "taux_alerte" in rows[0]


def test_biais_report_structure():
    from src.web.services import biais_report

    report = biais_report(score="sortie")
    assert report["total_groups"] >= 3
    assert len(report["categories"]) >= 2
    assert report["categories"][0]["rows"][0]["label"]
    assert "prevalence_pct" in report["categories"][0]["rows"][0]


def test_list_sejours_cisia_has_proba():
    data = list_sejours_cisia(page=1, page_size=5)
    assert data["total"] > 0
    item = data["items"][0]
    assert "proba_readmission_30j" in item
    assert "proba_pct" in item
    assert "NomFamille" in item
    assert "alerte_suivi_renforce" in item
    assert "DureeSejour" in item
    assert "stats" in data
    assert data["stats"]["total_scored"] > 0


def test_process_demo_context():
    from src.web.services import jury_parcours, process_demo_context

    data = jury_parcours()
    assert len(data["steps"]) == 5
    assert data["steps"][0].get("a_faire")
    ctx = process_demo_context(path="/cisia", tutorial_active=True)
    assert ctx["process_step"] == 1
    assert ctx["process_suivant"]["href"].startswith("/cisia/sejours")
    ctx2 = process_demo_context(path="/cisia/biais", tutorial_active=True)
    assert ctx2["process_step"] == 4
    assert ctx2["demo_spotlight"] == "biais-age"
    ctx_jury = process_demo_context(path="/cisia/jury", tutorial_active=True)
    assert ctx_jury["process_step"] == 0
    assert ctx_jury["demo_spotlight"] == "process-next"
    assert ctx_jury["process_suivant"]["href"] == "/cisia"
    ctx_off = process_demo_context(path="/cisia/sejours/SEJ001", tutorial_active=False)
    assert ctx_off["process_step"] == 0
    assert ctx_off["demo_spotlight"] is None
    assert ctx_off["demo_tutorial"] is False


def test_hub_and_parcours_routes():
    from fastapi.testclient import TestClient

    from src.web.app import app

    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Connexion" in r.text
    assert "login-gate" in r.text
    r_hub = client.get("/hub")
    assert r_hub.status_code == 200
    assert "CISIA Readmit" in r_hub.text or "démo commerciale" in r_hub.text
    assert client.get("/cisia").status_code == 200
    assert client.get("/cisia/biais").status_code == 200
    r_biais = client.get("/cisia/biais")
    assert "biais-categories" in r_biais.text
    assert "Audit des biais" in r_biais.text
    r_reg = client.get("/cisia/registre")
    assert r_reg.status_code == 200
    assert "registre-files" in r_reg.text
    assert "Registre des données" in r_reg.text
    r_jury = client.get("/cisia/jury")
    assert r_jury.status_code == 200
    assert "jury-timeline" in r_jury.text
    assert "Parcours jury" in r_jury.text
    assert 'action="/cisia/demo/start"' in r_jury.text
    assert "Lancer le parcours guidé" in r_jury.text
    r_start = client.post("/cisia/demo/start", follow_redirects=False)
    assert r_start.status_code == 302
    assert r_start.headers.get("location") == "/cisia"
    r_cisia = client.get("/cisia")
    assert "data-demo-nav" in r_cisia.text
    assert "Entrée" in r_cisia.text
    r_jury_on = client.get("/cisia/jury")
    assert "Tutoriel actif" in r_jury_on.text
    assert "data-demo-nav" in r_jury_on.text
    r_sej = client.get("/cisia/sejours")
    assert r_sej.status_code == 200
    assert "sejours-list" in r_sej.text
    assert "sejour-card" in r_sej.text
    data = list_sejours_cisia(page=1, page_size=1)
    sej = data["items"][0]["SejourID"]
    r_detail = client.get(f"/cisia/sejours/{sej}")
    assert r_detail.status_code == 200
    assert "sejour-fiche" in r_detail.text
    assert "Pourquoi ce risque" in r_detail.text
    assert client.get("/cisia/jury").status_code == 200
    assert client.get("/soignant").status_code == 200
    r_lits = client.get("/soignant/lits")
    assert r_lits.status_code == 200
    assert "Tous les lits" in r_lits.text
    assert "data-lits-page" in r_lits.text
    api_lits = client.get("/api/lits?page_size=3")
    assert api_lits.status_code == 200
    payload = api_lits.json()
    assert payload["total"] > 0
    assert len(payload["items"]) <= 3
    assert "filters" in payload
    sej = payload["items"][0]["SejourID"]
    r_fiche = client.get(f"/soignant/sejours/{sej}")
    assert r_fiche.status_code == 200
    assert "fiche-patient-page" in r_fiche.text
    assert "Prenom" not in r_fiche.text or "Prénom" in r_fiche.text
    r2 = client.get("/sejours", follow_redirects=False)
    assert r2.status_code in (301, 302, 307, 308)
    assert "/cisia/sejours" in r2.headers.get("location", "")


def test_pdf_export():
    from src.web.export_pdf import build_fiche_pdf

    data = list_sejours_cisia(a_risque=True, page=1, page_size=1)
    sej = data["items"][0]["SejourID"]
    detail = predict_sejour(sej)
    pdf = build_fiche_pdf(detail)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_auth_redirect_with_session(monkeypatch):
    monkeypatch.setenv("CISIA_AUTH", "1")
    import importlib

    import src.web.app as app_mod

    importlib.reload(app_mod)
    from fastapi.testclient import TestClient

    client = TestClient(app_mod.app)
    r = client.get("/cisia", follow_redirects=False)
    assert r.status_code == 302
    assert "/?next=" in r.headers.get("location", "") or "/login" in r.headers.get("location", "")
    r2 = client.post("/login/guest", follow_redirects=True)
    assert r2.status_code == 200
    assert "Tutoriel" in r2.text or "tutoriel" in r2.text
    client.post("/cisia/demo/terminer", data={"next": "/cisia"})
    r4 = client.get("/cisia")
    assert "Tutoriel · étape" not in r4.text
    data = list_sejours_cisia(page=1, page_size=1)
    sej = data["items"][0]["SejourID"]
    r5 = client.get(f"/cisia/sejours/{sej}")
    assert r5.status_code == 200
    assert "Tutoriel · étape 3" not in r5.text
    assert 'data-demo-spotlight="' not in r5.text
    client.post("/login/guest", follow_redirects=False)
    r6 = client.get("/cisia")
    assert "Tutoriel · étape" not in r6.text
    monkeypatch.setenv("CISIA_AUTH", "0")
    importlib.reload(app_mod)


def test_auth_credentials():
    from src.web.auth import guest_session, verify_credentials

    user = verify_credentials("demo@cisia.fr", "Readmit2026")
    assert user is not None
    assert user["role"] == "Coordinateur sortie"
    assert verify_credentials("demo@cisia.fr", "wrong") is None
    guest = guest_session()
    assert guest["guest"] is True


def test_health_page_html_without_data():
    from fastapi.testclient import TestClient

    from src.web.app import app

    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Opérationnel" in r.text or "Dégradé" in r.text
    assert "aucune donnée patient" in r.text.lower()
    assert "cisia-logo.png" in r.text
    assert "Retour à" not in r.text


def test_health_json_minimal():
    from fastapi.testclient import TestClient

    from src.web.app import app

    client = TestClient(app)
    r = client.get("/api/health", headers={"Accept": "application/json"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"ok", "degraded"}
    assert "version" in data
    assert "overview" not in data
    assert "n_sejours" not in data
