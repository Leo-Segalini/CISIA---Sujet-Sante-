from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.data.paths import ProjectPaths
from src.model.metrics import best_f2_threshold, classification_metrics
from src.model.prepare import by_split

FRENCH_STOP = [
    "le",
    "la",
    "les",
    "de",
    "des",
    "du",
    "un",
    "une",
    "et",
    "en",
    "pour",
    "par",
    "au",
    "aux",
    "ce",
    "cette",
    "son",
    "sa",
    "est",
    "a",
    "à",
]


def build_text_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=4000,
                    ngram_range=(1, 2),
                    min_df=2,
                    stop_words=FRENCH_STOP,
                ),
            ),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train_text_model(
    documents: pd.DataFrame,
    features: pd.DataFrame,
    *,
    paths: ProjectPaths,
) -> dict:
    """Entraîne un classifieur de langue sur CR masqués, split patient du parquet."""
    df = features[["SejourID", "split", "Readmission30j"]].merge(
        documents, on="SejourID", how="inner"
    )
    X = df[["document"]].copy()
    y = df["Readmission30j"].astype(int)
    split = df["split"].astype(str)
    X_tr, y_tr = by_split(X, y, split, "train")
    X_va, y_va = by_split(X, y, split, "val")
    X_te, y_te = by_split(X, y, split, "test")
    pipe = build_text_pipeline()
    pipe.fit(X_tr["document"], y_tr)
    p_va = pipe.predict_proba(X_va["document"])[:, 1]
    p_te = pipe.predict_proba(X_te["document"])[:, 1]
    thr = best_f2_threshold(y_va, p_va)
    report = {
        "modele": "tfidf_logistique",
        "justification": (
            "Modèle de langue statistique entraîné localement sur CR masqués. "
            "Adapté à n faible et textes courts (~180 caractères). "
            "Split patient identique au modèle tabulaire."
        ),
        "val": classification_metrics(y_va, p_va, thr),
        "test": classification_metrics(y_te, p_te, thr),
    }
    paths.ensure_data_dirs()
    joblib.dump(pipe, paths.models / "cr_tfidf.joblib")
    (paths.models / "cr_tfidf_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
