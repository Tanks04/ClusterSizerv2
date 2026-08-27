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


def test_v6_unit_price_migrates_to_price_preferring_unit_price(tmp_path):
    """v6 files had separate unit_cost/unit_price (a sales-quote-style
    split); v7 simplified to one plain `price` field. Migration should
    prefer the old unit_price (closer in spirit to "what gets paid")
    over unit_cost, so upgrading doesn't silently zero out data."""
    from src.models.server import Server

    project = ClusterProject(name="Migration test")
    project.servers.append(Server.create_default())
    path = tmp_path / "v6.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["servers"][0]["unit_cost"] = 12000.0
    raw["servers"][0]["unit_price"] = 18000.0
    del raw["servers"][0]["price"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].price == 18000.0


def test_v6_unit_cost_only_migrates_when_unit_price_missing(tmp_path):
    """Falls back to unit_cost if unit_price was never set, rather than
    losing the data entirely."""
    from src.models.server import Server

    project = ClusterProject(name="Migration test 2")
    project.servers.append(Server.create_default())
    path = tmp_path / "v6b.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["servers"][0]["unit_cost"] = 12000.0
    del raw["servers"][0]["price"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].price == 12000.0


def test_v6_storage_shelf_price_also_migrates(tmp_path):
    from src.models.storage import Storage, StorageShelf

    project = ClusterProject(name="Shelf migration")
    storage = Storage.create_default()
    storage.expansion_shelves = [StorageShelf(name="shelf-1", price=0.0)]
    project.storages.append(storage)
    path = tmp_path / "v6c.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["storages"][0]["unit_price"] = 50000.0
    del raw["storages"][0]["price"]
    raw["storages"][0]["expansion_shelves"][0]["unit_price"] = 9500.0
    del raw["storages"][0]["expansion_shelves"][0]["price"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].price == 50000.0
    assert loaded.project.storages[0].expansion_shelves[0].price == 9500.0


def test_v6_service_line_items_absent_gives_empty_maintenance_items(tmp_path):
    """v6 files have no `maintenance_items` key at all (the concept
    didn't exist yet) - must load fine with an empty list, not crash."""
    project = ClusterProject(name="Pre-maintenance")
    path = tmp_path / "v6d.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["maintenance_items"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.maintenance_items == []


def test_hci_storage_round_trip(tmp_path):
    from src.models.server import Server
    from src.models.storage import Storage

    project = ClusterProject(name="HCI test")
    server = Server.create_default()
    server.name = "esxi-01"
    server.local_disk_raw_tb = 20.0
    project.servers.append(server)

    storage = Storage.create_default()
    storage.name = "vsan-cluster-01"
    storage.vendor = "VMware"
    storage.model = "vSAN"
    storage.is_hci = True
    storage.hci_server_uids = [server.uid]
    project.storages.append(storage)

    path = tmp_path / "hci.clsz"
    project_repository.save_project(project, path, Thresholds())

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].is_hci is True
    assert loaded.project.storages[0].hci_server_uids == [server.uid]
    assert loaded.project.servers[0].local_disk_raw_tb == 20.0


def test_v6_file_without_hci_fields_defaults_correctly(tmp_path):
    """v6 files predate is_hci/hci_server_uids/local_disk_raw_tb - must
    load fine with the new defaults (False/empty/0), not crash."""
    from src.models.server import Server
    from src.models.storage import Storage

    project = ClusterProject(name="Pre-HCI")
    project.servers.append(Server.create_default())
    project.storages.append(Storage.create_default())
    path = tmp_path / "v6e.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["servers"][0]["local_disk_raw_tb"]
    del raw["storages"][0]["is_hci"]
    del raw["storages"][0]["hci_server_uids"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].local_disk_raw_tb == 0.0
    assert loaded.project.storages[0].is_hci is False
    assert loaded.project.storages[0].hci_server_uids == []


def test_deployment_model_round_trip(tmp_path):
    project = ClusterProject(name="Hybrid deployment test")
    project.dr_deployment_model = "Cloud"
    path = tmp_path / "hybrid.clsz"
    project_repository.save_project(project, path, Thresholds())

    loaded = project_repository.load_project(path)

    assert loaded.project.primary_deployment_model == "On-Premise"
    assert loaded.project.dr_deployment_model == "Cloud"


def test_v6_file_without_deployment_model_defaults_to_on_premise(tmp_path):
    """Files predating this feature have neither field at all - must
    load fine with the On-Premise default, not crash."""
    project = ClusterProject(name="Pre-deployment-model")
    path = tmp_path / "v6f.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["primary_deployment_model"]
    del raw["dr_deployment_model"]
    raw["schema_version"] = 6
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.primary_deployment_model == "On-Premise"
    assert loaded.project.dr_deployment_model == "On-Premise"
