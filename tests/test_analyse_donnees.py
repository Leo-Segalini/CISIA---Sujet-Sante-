"""Tests analyse données (cohorte, nulls, temporalité, patho)."""

from src.data.analyse_donnees import build_analyse_complete, cohort_training_summary
from src.data.cohort import filter_domicile
from src.data.load import load_csv
from src.data.paths import ProjectPaths, get_project_root


def test_deces_exclus_de_la_cohorte():
    paths = ProjectPaths(root=get_project_root())
    sej = load_csv(paths, "sejours.csv", from_raw=False)
    elig = filter_domicile(sej)
    assert (elig["ModeSortie"] == "Domicile").all()
    assert (elig["ModeSortie"] == "Deces").sum() == 0
    summary = cohort_training_summary(sej)
    assert summary["n_deces_exclus"] == int((sej["ModeSortie"] == "Deces").sum())
    assert summary["n_eligibles_entrainement"] == len(elig)


def test_build_analyse_complete_structure():
    paths = ProjectPaths(root=get_project_root())
    a = build_analyse_complete(paths)
    assert "cohorte" in a
    assert "nulls_sentinelles" in a
    assert "temporalite" in a
    assert "resume_fichiers" in a
    assert "stats_qualite" in a
    assert len(a["stats_qualite"]["categories"]) == 4
    assert a["stats_qualite"]["categories"][0]["id"] == "exclus"
    assert len(a["resume_fichiers"]) == 11
    assert a["temporalite"]["sejours"]["sortie_avant_admission"] == 0
    assert a["temporalite"]["evenements"]
    # Actes : beaucoup hors fenêtre (données synthétiques pédagogiques)
    actes = next(e for e in a["temporalite"]["evenements"] if e["fichier"] == "actes.csv")
    assert actes["n_hors_fenetre_sejour"] > 0
