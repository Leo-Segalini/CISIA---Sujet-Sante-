from src.data.paths import ProjectPaths, get_project_root
from src.data.registry import CSV_FILES


def test_project_root_contains_sources():
    root = get_project_root()
    assert (root / "patients.csv").exists()
    assert (root / "sejours.csv").exists()


def test_ensure_data_dirs_creates_tree(tmp_path):
    (tmp_path / "Sujet.md").write_text("x", encoding="utf-8")
    (tmp_path / "patients.csv").write_text("PatientID\n", encoding="utf-8")
    paths = ProjectPaths(root=tmp_path)
    paths.ensure_data_dirs()
    assert paths.raw.is_dir()
    assert paths.vault.is_dir()
    assert paths.pseudonymise.is_dir()
    assert paths.curated.is_dir()
    assert paths.models.is_dir()
    assert len(CSV_FILES) == 11
