from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.identity import persist_identity_split, split_identity_and_pseudonymise
from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root
from src.nlp.guardrails import grounded_justification, hallucination_rate, identity_leak
from src.nlp.local_llm import generate_justification, gguf_path, try_load_llama
from src.nlp.masking import documents_par_sejour, mask_comptes_rendus
from src.nlp.text_model import train_text_model
import pandas as pd


def main() -> None:
    paths = ProjectPaths(root=get_project_root())
    paths.ensure_data_dirs()
    patients = load_csv(paths, "patients.csv", from_raw=False)
    vault, _ = split_identity_and_pseudonymise(patients)
    persist_identity_split(paths, vault, _)
    sejours = load_csv(paths, "sejours.csv", from_raw=False)
    cr = load_csv(paths, "comptes_rendus.csv", from_raw=False)
    masked = mask_comptes_rendus(cr, vault, sejours)
    docs = documents_par_sejour(masked)
    feats = paths.curated / "features_score_sortie.parquet"
    if not feats.exists():
        raise FileNotFoundError("Lancer d'abord scripts/run_pipeline.py")
    features = pd.read_parquet(feats)
    report = train_text_model(docs, features, paths=paths)

    names = vault["NomPrenom"].dropna().astype(str).tolist()
    sample = docs.merge(features[["SejourID"]], on="SejourID").head(20)
    llm = try_load_llama(gguf_path(paths.models))
    rows = []
    for _, row in sample.iterrows():
        extractive = grounded_justification(row["document"])
        generated = extractive
        backend = "extractif"
        if llm is not None:
            generated = generate_justification(llm, row["document"])
            backend = "llama.cpp"
        leak = identity_leak(generated, names)
        rows.append(
            {
                "SejourID": row["SejourID"],
                "backend": backend,
                "justification": generated,
                "fuite_identite": bool(leak),
                "taux_hallucination": hallucination_rate(row["document"], generated),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(paths.models / "cr_justifications_echantillon.csv", index=False)
    summary = {
        "tfidf": report,
        "llm_backend": "llama.cpp" if llm is not None else "extractif (GGUF ou llama-cpp absent)",
        "n_echantillon": int(len(out)),
        "fuite_identite_n": int(out["fuite_identite"].sum()),
        "hallucination_moyenne": float(out["taux_hallucination"].mean()),
    }
    (paths.models / "cr_llm_rapport.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:2500])


if __name__ == "__main__":
    main()
