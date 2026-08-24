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
    assert project_repository.SCHEMA_VERSION == 5


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


def test_storage_shelves_round_trip_as_real_objects_not_dicts(tmp_path):
    """_build() only does a shallow field filter - Storage.expansion_shelves
    needed a dedicated reconstruction step (_build_storage()) or shelves
    would come back as plain dicts, breaking .rack_units/.power_watts
    attribute access."""
    from src.models.backup_destination import BackupDestination  # noqa: F401 - keep import group consistent
    from src.models.storage import Storage, StorageShelf

    project = ClusterProject(name="Rack round trip")
    storage = Storage.create_default()
    storage.name = "san-01"
    storage.rack_units = 4
    storage.power_watts = 1200.0
    storage.expansion_shelves = [StorageShelf(name="shelf-1", rack_units=2, power_watts=400.0)]
    project.storages.append(storage)

    path = tmp_path / "rack.clsz"
    project_repository.save_project(project, path, Thresholds())

    loaded = project_repository.load_project(path)
    loaded_storage = loaded.project.storages[0]

    assert loaded_storage.rack_units == 4
    assert loaded_storage.power_watts == 1200.0
    assert len(loaded_storage.expansion_shelves) == 1

    shelf = loaded_storage.expansion_shelves[0]
    assert isinstance(shelf, StorageShelf)
    assert shelf.rack_units == 2
    assert loaded_storage.total_rack_units == 6


def test_v4_file_without_rack_fields_loads_with_defaults(tmp_path):
    """A .clsz saved before schema v5 has no rack_units/power_watts/
    expansion_shelves keys at all - must load fine with defaults, not crash."""
    from src.models.server import Server

    project = ClusterProject(name="Pre-rack")
    project.servers.append(Server.create_default())
    path = tmp_path / "v4.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    for server in raw["servers"]:
        del server["rack_units"]
        del server["power_watts"]
    for storage in raw["storages"]:
        del storage["rack_units"]
        del storage["power_watts"]
        del storage["expansion_shelves"]
    raw["schema_version"] = 4
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].rack_units == 0
    assert loaded.project.servers[0].power_watts == 0.0
