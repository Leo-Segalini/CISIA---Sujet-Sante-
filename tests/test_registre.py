from src.data.paths import ProjectPaths, get_project_root
from src.data.registre import (
    assert_complements_insee_enregistres,
    assert_justifications,
    assert_registre_covers_sources,
    build_source_column_index,
    load_registre,
)
from src.data.territoire import build_complements_from_sujet, write_complements
from src.data.load import load_csv


def test_registre_covers_all_columns():
    paths = ProjectPaths(root=get_project_root())
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    index = build_source_column_index(paths)
    assert_registre_covers_sources(registre, index)
    assert_justifications(registre)


def test_complements_insee_differencies():
    paths = ProjectPaths(root=get_project_root())
    sujet = load_csv(paths, "territoire_insee.csv", from_raw=False)
    write_complements(paths, sujet)
    comp = build_complements_from_sujet(sujet)
    assert "INSEE_ajoute_PopulationLegale" in comp.columns
    assert (comp["origine_ligne"] == "insee_ajoute").all()
    # Le CSV sujet n'est pas modifié
    assert list(sujet.columns) == [
        "Commune",
        "CodePostal",
        "IndiceDefavorisation",
        "DensiteMedicale",
        "PopulationCommune",
    ]
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    assert_complements_insee_enregistres(registre, paths)
    insee_rows = registre.loc[registre["origine_donnee"] == "insee_ajoute"]
    assert len(insee_rows) >= 5
