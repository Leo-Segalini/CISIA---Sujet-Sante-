from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Démo CISIA : le LLM local doit tourner (utilité IA). CISIA_LLM=0 uniquement pour tests.
os.environ.setdefault("CISIA_LLM", "1")

import uvicorn


def main() -> None:
    # Charger le LLM depuis le process principal (spawn multiprocessing OK)
    from src.web.services import get_store

    print("Chargement des données et de l’assistant IA local…")
    store = get_store()
    store.try_start_llm()
    print(f"IA locale : {store.llm_statut}")
    uvicorn.run(
        "src.web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
