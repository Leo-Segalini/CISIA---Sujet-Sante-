from __future__ import annotations

from pathlib import Path

# Préféré : 3B Q4 — meilleur français / justifications, encore tenable CPU Mac 16 Go.
# Repli : 1.5B déjà présent si le 3B n’est pas téléchargé.
GGUF_CANDIDATES: list[tuple[str, str]] = [
    ("Qwen/Qwen2.5-3B-Instruct-GGUF", "qwen2.5-3b-instruct-q4_k_m.gguf"),
    ("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
]

# Compat scripts / docs : cible de téléchargement par défaut = 3B
GGUF_REPO, GGUF_FILE = GGUF_CANDIDATES[0]


def resolve_gguf(models_dir: Path) -> Path | None:
    """Premier GGUF disponible (3B puis 1.5B)."""
    for _, filename in GGUF_CANDIDATES:
        path = models_dir / "gguf" / filename
        if path.exists():
            return path
    return None


def gguf_path(models_dir: Path) -> Path:
    """Chemin préféré (3B) ; pour téléchargement. Préférer resolve_gguf à l’exécution."""
    found = resolve_gguf(models_dir)
    if found is not None:
        return found
    return models_dir / "gguf" / GGUF_FILE


def try_load_llama(model_file: Path, n_ctx: int = 2048, *, n_gpu_layers: int = -1):
    """Charge llama.cpp dans le process courant (tests / scripts). Préférer LlmBridge en webapp."""
    if not model_file.exists():
        return None
    try:
        from llama_cpp import Llama
    except ImportError:
        return None
    return Llama(
        model_path=str(model_file),
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )


def _run_prompt(llm, prompt: str, *, max_tokens: int) -> str:
    if type(llm).__name__ == "LlmBridge":
        return (llm.generate(prompt, max_tokens=max_tokens) or "").strip()
    out = llm(
        prompt,
        max_tokens=max_tokens,
        temperature=0.0,
        stop=["<|im_end|>", "<|im_start|>"],
    )
    return (out["choices"][0]["text"] or "").strip()


def prompt_justification(document: str) -> str:
    from src.nlp.guardrails import SYSTEM_PROMPT

    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\nCompte-rendu:\n{document[:900]}\n\n"
        f"Rédige exactement 2 phrases en français simple, en reprenant uniquement "
        f"des faits présents dans le texte (pas de laboratoire inventé, pas de diagnostic "
        f"hors texte).<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


def prompt_brief_urgence(chambre: str, vitals: dict, document: str) -> str:
    vit = ", ".join(
        f"{k}={v:.1f}" for k, v in vitals.items() if v is not None
    )
    return (
        "<|im_start|>system\nTu parles à une infirmière, en français simple, "
        "sans jargon informatique. 1 phrase. N'invente aucun chiffre hors de la liste.<|im_end|>\n"
        f"<|im_start|>user\nChambre {chambre}. Constantes: {vit}. "
        f"Notes: {document[:280]}\nDis clairement s'il faut passer voir le patient maintenant.<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def generate_justification(llm, document: str, *, max_tokens: int = 120) -> str:
    from src.nlp.guardrails import grounded_justification, hallucination_rate

    text = _run_prompt(llm, prompt_justification(document), max_tokens=max_tokens)
    if hallucination_rate(document, text) > 0.15 or not text:
        return grounded_justification(document)
    return text


def generate_brief_text(llm, chambre: str, vitals: dict, document: str) -> str:
    from src.nlp.guardrails import hallucination_rate

    prompt = prompt_brief_urgence(chambre, vitals, document)
    text = _run_prompt(llm, prompt, max_tokens=60)
    src = prompt + " " + document
    if text and hallucination_rate(src, text) <= 0.35:
        return text
    spo2 = vitals.get("SpO2")
    if spo2 is not None and spo2 < 92:
        return (
            f"Saturation à {spo2:.0f} % en chambre {chambre} : "
            "passez voir le patient maintenant et prévenez le médecin."
        )
    return (
        f"Alerte en chambre {chambre} : vérifiez les constantes "
        "et passez au lit sans attendre."
    )
