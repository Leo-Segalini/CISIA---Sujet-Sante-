from src.data.paths import ProjectPaths, get_project_root
from src.data.registre import (
    assert_justifications,
    assert_registre_covers_sources,
    build_source_column_index,
    load_registre,
)


def test_registre_covers_all_columns():
    paths = ProjectPaths(root=get_project_root())
    registre = load_registre(paths.registres / "registre_colonnes.csv")
    index = build_source_column_index(paths)
    assert_registre_covers_sources(registre, index)
    assert_justifications(registre)
