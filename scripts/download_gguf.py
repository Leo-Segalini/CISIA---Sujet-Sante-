from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import ProjectPaths, get_project_root
from src.nlp.local_llm import GGUF_CANDIDATES, GGUF_FILE, GGUF_REPO, resolve_gguf


def main() -> None:
    """Télécharge le GGUF préféré (3B). N'envoie aucune donnée patient."""
    paths = ProjectPaths(root=get_project_root())
    dest_dir = paths.models / "gguf"
    dest_dir.mkdir(parents=True, exist_ok=True)

    preferred = dest_dir / GGUF_FILE
    if preferred.exists():
        print(f"déjà présent (préféré): {preferred}")
        return

    found = resolve_gguf(paths.models)
    if found is not None:
        print(f"repli déjà présent: {found}")
        print(f"pour upgrader: supprimer le repli ou lancer le téléchargement du 3B")

    print(f"téléchargement Hub: {GGUF_REPO} / {GGUF_FILE}")
    print("(poids publics — HF_TOKEN optionnel pour les quotas)")
    from huggingface_hub import hf_hub_download

    downloaded = hf_hub_download(
        repo_id=GGUF_REPO,
        filename=GGUF_FILE,
        local_dir=str(dest_dir),
    )
    print(f"téléchargé: {downloaded}")
    print("candidats supportés:")
    for repo, name in GGUF_CANDIDATES:
        print(f"  - {repo} → {name}")


if __name__ == "__main__":
    main()
