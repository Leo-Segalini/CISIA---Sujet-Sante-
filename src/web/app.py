from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.web.auth import (
    auth_enabled,
    clear_tutorial_done_cookie,
    demo_accounts_hint,
    guest_session,
    is_demo_tutorial_active,
    mark_tutorial_done_on_response,
    public_path,
    session_secret,
    should_auto_start_tutorial,
    start_demo_tutorial,
    verify_credentials,
)
from src.data.paths import ProjectPaths, get_project_root
from src.web.export_pdf import build_fiche_pdf
from src.web.ml_api import router as ml_router
from src.web.model_watch import start_model_watcher
from src.web.services import (
    admettre_lit,
    biais_report,
    biais_rows,
    get_store,
    jury_parcours,
    list_sejours,
    list_sejours_cisia,
    lits_filter_options,
    live_board,
    nettoyer_lit,
    overview,
    predict_sejour,
    process_demo_context,
    registre_report,
    registre_rows,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = Jinja2Templates(directory=str(ROOT / "webapp" / "templates"))
STATIC = ROOT / "webapp" / "static"

app = FastAPI(
    title="CISIA Santé — Démo locale",
    description="Deux parcours : CISIA (réadmission 30 j) et démo soignant. Données synthétiques.",
    version="0.9.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
app.include_router(ml_router)


def _session_user(request: Request):
    if "session" not in request.scope:
        return None
    return request.session.get("user")


def _user_ctx(request: Request) -> dict:
    return {"current_user": _session_user(request)}


def _cisia_ctx(request: Request, **extra) -> dict:
    """Contexte commun parcours CISIA + barre de process."""
    sej = extra.get("sejour_id") or extra.get("d", {}).get("SejourID")
    tutorial = is_demo_tutorial_active(request.session, request)
    proc = process_demo_context(
        path=str(request.url.path),
        sejour_id=sej,
        tutorial_active=tutorial,
    )
    ctx = {
        "parcours": "cisia",
        "demo_tutorial": tutorial,
        **proc,
        **_user_ctx(request),
        **extra,
    }
    return ctx


@app.middleware("http")
async def require_login(request: Request, call_next):
    if not auth_enabled() or public_path(request.url.path):
        return await call_next(request)
    user = _session_user(request)
    if user:
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return Response(
            '{"detail":"Non authentifié"}',
            status_code=401,
            media_type="application/json",
        )
    nxt = quote(str(request.url.path))
    if request.url.query:
        nxt = quote(f"{request.url.path}?{request.url.query}")
    return RedirectResponse(f"/?next={nxt}", status_code=302)


# SessionMiddleware en dernier = exécuté en premier à la réception (requis pour request.session).
app.add_middleware(SessionMiddleware, secret_key=session_secret(), https_only=False)


@app.on_event("startup")
def _startup() -> None:
    start_model_watcher()

    def _warm() -> None:
        try:
            store = get_store()
            if store._llm_bridge is None:
                store.try_start_llm()
            live_board(max_par_service=4)
        except Exception as exc:  # noqa: BLE001
            print(f"warm-up: {exc}")

    threading.Thread(target=_warm, daemon=True).start()


def _login_template(
    request: Request,
    *,
    next_url: str = "",
    error: str | None = None,
    email: str = "",
    status_code: int = 200,
):
    return TEMPLATES.TemplateResponse(
        request,
        "login.html",
        {
            "next_url": next_url,
            "accounts": demo_accounts_hint(),
            "error": error,
            "email": email,
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next_url: str = Query("", alias="next")):
    if _session_user(request):
        return RedirectResponse(next_url or "/cisia", status_code=302)
    return _login_template(request, next_url=next_url)


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
):
    user = verify_credentials(email, password)
    if not user:
        return _login_template(
            request,
            next_url=next,
            error="Identifiants incorrects. Utilisez un compte de démonstration.",
            email=email,
            status_code=401,
        )
    request.session["user"] = user
    return RedirectResponse(next or "/cisia", status_code=302)


@app.post("/login/guest")
def login_guest(request: Request):
    request.session["user"] = guest_session()
    if should_auto_start_tutorial(request):
        start_demo_tutorial(request.session)
    return RedirectResponse("/cisia", status_code=302)


@app.post("/cisia/demo/start")
def cisia_demo_start(request: Request):
    start_demo_tutorial(request.session)
    response = RedirectResponse("/cisia", status_code=302)
    clear_tutorial_done_cookie(response)
    return response


@app.post("/cisia/demo/terminer")
def cisia_demo_terminer(request: Request, next: str = Form("/cisia")):
    dest = next if next.startswith("/") else "/cisia"
    response = RedirectResponse(dest, status_code=302)
    mark_tutorial_done_on_response(response, request.session)
    return response


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@app.get("/hub", response_class=HTMLResponse)
def hub(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        "hub.html",
        {"parcours": "hub", "overview": overview(), **_user_ctx(request)},
    )


@app.get("/cisia", response_class=HTMLResponse)
def cisia_home(request: Request):
    tutorial = is_demo_tutorial_active(request.session, request)
    proc = process_demo_context(path="/cisia", tutorial_active=tutorial)
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "parcours": "cisia",
            "overview": overview(),
            "demo_tutorial": tutorial,
            **_user_ctx(request),
            **proc,
        },
    )


@app.get("/cisia/jury", response_class=HTMLResponse)
def cisia_jury(request: Request, etape: int = Query(1, ge=1, le=5)):
    data = jury_parcours()
    ov = overview()
    return TEMPLATES.TemplateResponse(
        request,
        "cisia_jury.html",
        _cisia_ctx(
            request,
            etape=etape,
            steps=data["steps"],
            sejour_exemple=data["sejour_exemple"],
            overview=ov,
        ),
    )


@app.get("/cisia/sejours", response_class=HTMLResponse)
def cisia_sejours(
    request: Request,
    q: str = "",
    a_risque: bool = False,
    page: int = Query(1, ge=1),
):
    tutorial = is_demo_tutorial_active(request.session, request)
    if tutorial and not q.strip():
        a_risque = True
    data = list_sejours_cisia(q=q, a_risque=a_risque, page=page)
    return TEMPLATES.TemplateResponse(
        request,
        "cisia_sejours.html",
        _cisia_ctx(request, data=data, q=q, a_risque=a_risque),
    )


@app.get("/cisia/sejours/{sejour_id}", response_class=HTMLResponse)
def cisia_sejour_detail(request: Request, sejour_id: str):
    try:
        detail = predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TEMPLATES.TemplateResponse(
        request,
        "cisia_sejour_detail.html",
        _cisia_ctx(request, d=detail, sejour_id=sejour_id),
    )


@app.get("/cisia/sejours/{sejour_id}/print", response_class=HTMLResponse)
def cisia_sejour_print(request: Request, sejour_id: str):
    try:
        detail = predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TEMPLATES.TemplateResponse(
        request,
        "fiche_print.html",
        {
            "d": detail,
            "generated_at": datetime.now(UTC).strftime("%d/%m/%Y %H:%M"),
        },
    )


@app.get("/cisia/sejours/{sejour_id}/export.pdf")
def cisia_sejour_pdf(sejour_id: str):
    try:
        detail = predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pdf_bytes = build_fiche_pdf(detail)
    safe_id = sejour_id.replace("/", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="CISIA_fiche_{safe_id}.pdf"',
        },
    )


@app.get("/cisia/registre", response_class=HTMLResponse)
def cisia_registre(
    request: Request, sensibilite: str = "", usage: str = "", origine: str = ""
):
    report = registre_report(sensibilite=sensibilite, usage=usage, origine=origine)
    return TEMPLATES.TemplateResponse(
        request,
        "registre.html",
        _cisia_ctx(
            request,
            report=report,
            rows=report["rows"],
            sensibilite=sensibilite,
            usage=usage,
            origine=origine,
        ),
    )


@app.get("/cisia/biais", response_class=HTMLResponse)
def cisia_biais(request: Request, score: str = "sortie"):
    report = biais_report(score=score)
    return TEMPLATES.TemplateResponse(
        request,
        "cisia_biais.html",
        _cisia_ctx(request, report=report, score=score, rows=report["rows"]),
    )


@app.get("/soignant", response_class=HTMLResponse)
def soignant_etage(request: Request):
    response = TEMPLATES.TemplateResponse(
        request,
        "etage.html",
        {"parcours": "soignant", "overview": overview(), "page_full_width": True, **_user_ctx(request)},
    )
    if request.session.get("demo_tutorial") == "active":
        mark_tutorial_done_on_response(response, request.session)
    return response


@app.get("/soignant/lits", response_class=HTMLResponse)
def soignant_lits(
    request: Request,
    q: str = "",
    etage: int | None = Query(None, ge=0, le=4),
    service: str = "",
    sexe: str = "",
    page: int = Query(1, ge=1),
):
    data = list_sejours(q=q, etage=etage, service=service, sexe=sexe, page=page)
    return TEMPLATES.TemplateResponse(
        request,
        "sejours.html",
        {
            "parcours": "soignant",
            "data": data,
            "q": q,
            "etage": etage,
            "service": service,
            "sexe": sexe,
            "filter_options": lits_filter_options(),
            **_user_ctx(request),
        },
    )


@app.get("/api/lits")
def api_lits(
    q: str = "",
    etage: int | None = Query(None, ge=0, le=4),
    service: str = "",
    sexe: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return list_sejours(
        q=q,
        etage=etage,
        service=service,
        sexe=sexe,
        page=page,
        page_size=page_size,
    )


@app.get("/soignant/sejours/{sejour_id}", response_class=HTMLResponse)
def soignant_sejour(request: Request, sejour_id: str):
    try:
        detail = predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TEMPLATES.TemplateResponse(
        request,
        "sejour_detail.html",
        {"parcours": "soignant", "d": detail, **_user_ctx(request)},
    )


@app.get("/sejours")
def redirect_sejours():
    return RedirectResponse("/cisia/sejours?a_risque=true", status_code=302)


@app.get("/sejours/{sejour_id}")
def redirect_sejour(sejour_id: str):
    return RedirectResponse(f"/cisia/sejours/{sejour_id}", status_code=302)


@app.get("/registre")
def redirect_registre():
    return RedirectResponse("/cisia/registre", status_code=302)


def _health_payload() -> dict:
    """État infrastructure uniquement — aucune donnée patient ni métrique modèle."""
    paths = ProjectPaths(root=get_project_root())
    llm_enabled = os.environ.get("CISIA_LLM", "0") == "1"

    def _bundle(name: str) -> bool:
        return (paths.models / f"{name}_bundle.joblib").exists()

    components = [
        {
            "id": "api",
            "label": "API web",
            "detail": "Serveur FastAPI joignable",
            "state": "ok",
            "state_label": "OK",
            "state_class": "ok",
            "icon": "dns",
        },
        {
            "id": "models_sortie",
            "label": "Modèle score sortie",
            "detail": "Bundle déployé sur disque",
            "state": "ok" if _bundle("score_sortie") else "missing",
            "state_label": "Prêt" if _bundle("score_sortie") else "Absent",
            "state_class": "ok" if _bundle("score_sortie") else "warn",
            "icon": "model_training",
        },
        {
            "id": "models_tele",
            "label": "Modèle score télé",
            "detail": "Bundle déployé sur disque",
            "state": "ok" if _bundle("score_tele") else "missing",
            "state_label": "Prêt" if _bundle("score_tele") else "Absent",
            "state_class": "ok" if _bundle("score_tele") else "warn",
            "icon": "monitor_heart",
        },
        {
            "id": "llm",
            "label": "LLM local",
            "detail": "Brief comptes-rendus (hors cloud)",
            "state": "enabled" if llm_enabled else "disabled",
            "state_label": "Activé" if llm_enabled else "Désactivé",
            "state_class": "off" if not llm_enabled else "ok",
            "icon": "psychology",
        },
        {
            "id": "auth",
            "label": "Authentification",
            "detail": "Protection des parcours CISIA / soignant",
            "state": "enabled" if auth_enabled() else "disabled",
            "state_label": "Activée" if auth_enabled() else "Désactivée",
            "state_class": "off",
            "icon": "lock",
        },
    ]

    critical = {"models_sortie", "models_tele"}
    degraded = any(c["id"] in critical and c["state"] != "ok" for c in components)

    now = datetime.now(UTC)
    return {
        "status": "degraded" if degraded else "ok",
        "version": app.version,
        "environment": "démo locale",
        "timestamp": now.isoformat(),
        "timestamp_display": now.strftime("%d/%m/%Y %H:%M UTC"),
        "components": components,
    }


@app.get("/api/health")
def health(request: Request, format: str | None = Query(None, alias="format")):
    payload = _health_payload()
    wants_json = (
        format == "json"
        or request.headers.get("accept", "").startswith("application/json")
    )
    if wants_json:
        return JSONResponse(
            {
                "status": payload["status"],
                "version": payload["version"],
                "environment": payload["environment"],
                "timestamp": payload["timestamp"],
            }
        )
    return TEMPLATES.TemplateResponse(
        request,
        "health.html",
        {"health_status": payload},
    )


@app.get("/api/live")
def api_live():
    return live_board()


@app.post("/api/lits/nettoyer")
def api_nettoyer_lit(payload: dict):
    try:
        return nettoyer_lit(
            service=str(payload.get("service") or ""),
            chambre=str(payload.get("chambre") or ""),
            lit=str(payload.get("lit") or ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/lits/admettre")
def api_admettre_lit(payload: dict):
    try:
        return admettre_lit(
            service=str(payload.get("service") or ""),
            chambre=str(payload.get("chambre") or ""),
            lit=str(payload.get("lit") or ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sejours/{sejour_id}/constantes")
def api_sejour_constantes(sejour_id: str, valides_only: bool = False):
    try:
        detail = predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    hist = detail["constantes_historique"]
    if valides_only:
        return {
            "SejourID": sejour_id,
            "total": hist["retenues"],
            "mesures": hist["mesures_retenues"],
            "plages_reference": hist["plages_reference"],
        }
    return {"SejourID": sejour_id, **hist}


@app.get("/api/sejours/{sejour_id}")
def api_sejour(sejour_id: str):
    try:
        return predict_sejour(sejour_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
