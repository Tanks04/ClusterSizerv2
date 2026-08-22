import json

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.backup_destination import BackupDestination
from src.persistence import project_repository


def test_thresholds_round_trip(tmp_path):
    project = ClusterProject(name="Round trip")
    thresholds = Thresholds(cpu_warning_ratio=3.5, ram_warning_ratio=0.7)

    path = tmp_path / "proj.clsz"
    project_repository.save_project(project, path, thresholds)

    loaded = project_repository.load_project(path)

    assert loaded.thresholds.cpu_warning_ratio == 3.5
    assert loaded.thresholds.ram_warning_ratio == 0.7
    assert project_repository.SCHEMA_VERSION == 4


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


def test_backup_destinations_round_trip(tmp_path):
    project = ClusterProject(name="Backup round trip")
    d = BackupDestination.create_default()
    d.name = "veeam-repo-01"
    d.destination_type = "Disk Appliance"
    d.is_immutable = True
    d.dedup_ratio = 5.0
    project.backup_destinations.append(d)

    path = tmp_path / "backup.clsz"
    project_repository.save_project(project, path, Thresholds())

    loaded = project_repository.load_project(path)

    assert len(loaded.project.backup_destinations) == 1
    assert loaded.project.backup_destinations[0].name == "veeam-repo-01"
    assert loaded.project.backup_destinations[0].is_immutable is True
    assert loaded.project.backup_destinations[0].effective_capacity_tb == \
        loaded.project.backup_destinations[0].raw_capacity_tb * 5.0


def test_v3_file_without_backup_destinations_loads_with_empty_list(tmp_path):
    """A .clsz saved before schema v4 has no "backup_destinations" key at
    all - must load fine with an empty list, not crash."""
    project = ClusterProject(name="Pre-backup")
    path = tmp_path / "v3.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["backup_destinations"]
    raw["schema_version"] = 3
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.backup_destinations == []
