import json

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.persistence import project_repository


def test_thresholds_round_trip(tmp_path):
    project = ClusterProject(name="Round trip")
    thresholds = Thresholds(cpu_warning_ratio=3.5, ram_warning_ratio=0.7)

    path = tmp_path / "proj.clsz"
    project_repository.save_project(project, path, thresholds)

    loaded = project_repository.load_project(path)

    assert loaded.thresholds.cpu_warning_ratio == 3.5
    assert loaded.thresholds.ram_warning_ratio == 0.7
    assert project_repository.SCHEMA_VERSION == 3


def test_v2_file_loads_with_default_thresholds(tmp_path):
    project = ClusterProject(name="Legacy")
    path = tmp_path / "legacy.clsz"
    project_repository.save_project(project, path, Thresholds())

    # Simulate a v2 file saved before thresholds existed.
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["thresholds"]
    raw["schema_version"] = 2
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.thresholds.cpu_warning_ratio == Thresholds().cpu_warning_ratio
