from __future__ import annotations

import pandas as pd


def bias_table(frame: pd.DataFrame, y_true: pd.Series, pred: pd.Series) -> pd.DataFrame:
    """Rappel et prévalence par groupe — la couleur n'est pas le seul signal."""
    out = frame.copy()
    out["_y"] = y_true.to_numpy()
    out["_p"] = pred.to_numpy()
    rows = []

    def add(label: str, mask: pd.Series) -> None:
        sub = out.loc[mask]
        if len(sub) == 0:
            return
        y = sub["_y"]
        p = sub["_p"]
        tp = int(((y == 1) & (p == 1)).sum())
        pos = int((y == 1).sum())
        rows.append(
            {
                "groupe": label,
                "n": int(len(sub)),
                "prevalence": float(y.mean()),
                "rappel": float(tp / pos) if pos else float("nan"),
                "taux_alerte": float(p.mean()),
            }
        )

    if "Sexe" in out.columns:
        for sexe, mask in out.groupby("Sexe").groups.items():
            add(f"Sexe={sexe}", out.index.isin(mask))

    if "age_admission" in out.columns:
        age = pd.to_numeric(out["age_admission"], errors="coerce")
        bins = pd.cut(age, bins=[0, 65, 80, 120], labels=["<65", "65-80", ">80"])
        for lab in pd.Series(bins).dropna().unique():
            add(f"age={lab}", bins == lab)

    if "IndiceDefavorisation" in out.columns:
        idx = pd.to_numeric(out["IndiceDefavorisation"], errors="coerce")
        tert = pd.qcut(idx, 3, labels=["T1_faible", "T2", "T3_eleve"], duplicates="drop")
        for lab in pd.Series(tert).dropna().unique():
            add(f"defav={lab}", tert == lab)

    return pd.DataFrame(rows)
