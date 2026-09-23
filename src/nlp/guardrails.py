from __future__ import annotations

import re

ALLOWED_EXTRA = {
    "patient",
    "sortie",
    "domicile",
    "surveillance",
    "risque",
    "réadmission",
    "readmission",
    "suivi",
    "fragilité",
    "fragilite",
}


def identity_leak(text: str, names: list[str]) -> list[str]:
    found = []
    low = text.lower()
    for name in names:
        n = str(name).strip()
        if len(n) >= 4 and n.lower() in low:
            found.append(n)
    return found


def hallucination_rate(source: str, generated: str) -> float:
    """Part des tokens générés (len≥5) absents du CR et du lexique autorisé."""
    src = set(re.findall(r"[a-zàâçéèêëîïôùûü]{5,}", source.lower()))
    gen = re.findall(r"[a-zàâçéèêëîïôùûü]{5,}", generated.lower())
    if not gen:
        return 0.0

    def covered(token: str) -> bool:
        if token in src or token in ALLOWED_EXTRA:
            return True
        # Variantes morphologiques simples (surveillance / surveillances)
        return any(token.startswith(s[:5]) or s.startswith(token[:5]) for s in src)

    bad = [t for t in gen if not covered(t)]
    return float(len(bad) / len(gen))


def grounded_justification(document: str, *, max_chars: int = 280) -> str:
    """Filet extractif : aucune invention — on recopie le CR masqué."""
    text = " ".join(document.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


SYSTEM_PROMPT = (
    "Tu es un assistant hospitalier local. Tu ne dois JAMAIS inventer un nom, "
    "un résultat de laboratoire ou un diagnostic absent du texte. "
    "Réponds en 2 phrases en français, uniquement à partir du compte-rendu."
)
