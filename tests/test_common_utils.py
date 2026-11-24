from pathlib import Path

from src.common.utils import get_project_root, get_paths


def test_project_root():
    root = get_project_root()

    assert root.is_absolute()
    assert (root / "src").is_dir()
    assert (root / "tests").is_dir()


def test_get_paths():
    paths = get_paths()

    assert paths["root"] == get_project_root()
    assert paths["data"] == get_project_root() / "data"
    assert paths["frames"] == get_project_root() / "data" / "frames"
    assert paths["results"] == get_project_root() / "results"
    assert paths["weights"] == get_project_root() / "weights"

    for path in paths.values():
        assert isinstance(path, Path)
        assert path.is_absolute()
