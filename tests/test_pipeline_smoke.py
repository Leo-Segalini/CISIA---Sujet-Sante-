from src.data.paths import ProjectPaths, get_project_root
from src.data.pipeline import run_pipeline


def test_pipeline_smoke():
    paths = ProjectPaths(root=get_project_root())
    out = run_pipeline(paths, horizon_tele=7)
    assert out["features_score_sortie"].exists()
    assert out["features_score_tele"].exists()
    import pandas as pd

    fs = pd.read_parquet(out["features_score_sortie"])
    assert "NomPrenom" not in fs.columns
    assert "Readmission30j" in fs.columns
    assert "split" in fs.columns
