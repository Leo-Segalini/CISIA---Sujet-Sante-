from __future__ import annotations

import os
from typing import Any

# Comptes fictifs — démo commerciale uniquement (jamais en production réelle).
_DEMO_USERS: dict[str, dict[str, Any]] = {
    "demo@cisia.fr": {
        "password": "Readmit2026",
        "name": "Dr. Martin Dupont",
        "role": "Coordinateur sortie",
        "etablissement": "CHU CISIA — démo",
    },
    "admin@cisia.fr": {
        "password": "Admin2026",
        "name": "Sophie Bernard",
        "role": "DPO / Conformité",
        "etablissement": "CHU CISIA — démo",
    },
}


def auth_enabled() -> bool:
    return os.environ.get("CISIA_AUTH", "1") != "0"


def session_secret() -> str:
    return os.environ.get(
        "CISIA_SESSION_SECRET",
        "cisia-demo-local-secret-ne-pas-utiliser-en-prod",
    )


def public_path(path: str) -> bool:
    if path.startswith("/static"):
        return True
    if path.startswith("/api/ml"):
        return True
    return path in {"/", "/login", "/login/guest", "/api/health"}


def verify_credentials(email: str, password: str) -> dict[str, Any] | None:
    key = email.strip().lower()
    row = _DEMO_USERS.get(key)
    if not row or row["password"] != password:
        return None
    return {
        "email": key,
        "name": row["name"],
        "role": row["role"],
        "etablissement": row["etablissement"],
    }


def guest_session() -> dict[str, Any]:
    return {
        "email": "demo@cisia.fr",
        "name": "Visiteur salon",
        "role": "Démonstration",
        "etablissement": "CHU CISIA — démo",
        "guest": True,
    }


def demo_accounts_hint() -> list[dict[str, str]]:
    return [
        {"email": email, "password": data["password"], "role": data["role"]}
        for email, data in _DEMO_USERS.items()
    ]


TUTORIAL_SESSION_KEY = "demo_tutorial"
TUTORIAL_DONE_COOKIE = "cisia_tutorial_done"
TUTORIAL_COOKIE_MAX_AGE = 365 * 24 * 3600


def tutorial_done_in_browser(request) -> bool:
    return request.cookies.get(TUTORIAL_DONE_COOKIE) == "1"


def is_demo_tutorial_active(session: dict, request=None) -> bool:
    if session.get(TUTORIAL_SESSION_KEY) != "active":
        return False
    if request is not None and tutorial_done_in_browser(request):
        return False
    return True


def is_demo_tutorial_done(session: dict) -> bool:
    return session.get(TUTORIAL_SESSION_KEY) == "done"


def should_auto_start_tutorial(request) -> bool:
    """Tutoriel guidé uniquement si jamais terminé sur ce navigateur."""
    return not tutorial_done_in_browser(request)


def start_demo_tutorial(session: dict) -> None:
    session[TUTORIAL_SESSION_KEY] = "active"


def complete_demo_tutorial(session: dict) -> None:
    session[TUTORIAL_SESSION_KEY] = "done"


def mark_tutorial_done_on_response(response, session: dict):
    """Marque le tutoriel terminé (session + cookie navigateur)."""
    complete_demo_tutorial(session)
    response.set_cookie(
        TUTORIAL_DONE_COOKIE,
        "1",
        max_age=TUTORIAL_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_tutorial_done_cookie(response) -> None:
    response.delete_cookie(TUTORIAL_DONE_COOKIE)
