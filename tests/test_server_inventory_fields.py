"""Tests for Server's new inventory fields (Serial Number, BMC IP,
Hypervisor vendor/version) and BackupDestination's Location field and
Cloud destination type."""

from src.models.server import Server, HYPERVISOR_VENDORS
from src.models.backup_destination import BackupDestination, DESTINATION_TYPES
from src.persistence import csv_io, project_repository
from src.models.cluster_project import ClusterProject
from src.calculations.thresholds import Thresholds


def test_cloud_is_a_valid_destination_type():
    assert "Cloud" in DESTINATION_TYPES


def test_server_new_fields_default_to_empty():
    s = Server.create_default()
    assert s.serial_number == ""
    assert s.bmc_ip == ""
    assert s.hypervisor_vendor == ""
    assert s.hypervisor_version == ""


def test_backup_destination_location_defaults_to_empty():
    d = BackupDestination.create_default()
    assert d.location == ""


def test_hypervisor_vendors_includes_expected_options():
    assert "VMware (ESXi / vSphere)" in HYPERVISOR_VENDORS
    assert "Microsoft Hyper-V" in HYPERVISOR_VENDORS
    assert "" in HYPERVISOR_VENDORS  # blank/unset is a valid selection


def test_server_csv_round_trip_for_new_fields(tmp_path):
    s = Server.create_default()
    s.serial_number = "SN12345"
    s.bmc_ip = "10.10.99.10"
    s.hypervisor_vendor = "VMware (ESXi / vSphere)"
    s.hypervisor_version = "8.0 U2"

    path = tmp_path / "servers.csv"
    csv_io.export_servers(path, [s])
    loaded = csv_io.import_servers(path)

    assert loaded[0].serial_number == "SN12345"
    assert loaded[0].bmc_ip == "10.10.99.10"
    assert loaded[0].hypervisor_vendor == "VMware (ESXi / vSphere)"
    assert loaded[0].hypervisor_version == "8.0 U2"


def test_backup_destination_csv_round_trip_for_location_and_cloud(tmp_path):
    d = BackupDestination.create_default()
    d.destination_type = "Cloud"
    d.location = "Azure Blob Storage - West Europe"

    path = tmp_path / "backup.csv"
    csv_io.export_backup_destinations(path, [d])
    loaded = csv_io.import_backup_destinations(path)

    assert loaded[0].destination_type == "Cloud"
    assert loaded[0].location == "Azure Blob Storage - West Europe"


def test_clsz_round_trip_for_new_fields(tmp_path):
    project = ClusterProject(name="Inventory test")
    s = Server.create_default()
    s.serial_number = "SN12345"
    s.hypervisor_vendor = "Nutanix AHV"
    project.servers.append(s)
    d = BackupDestination.create_default()
    d.location = "Iron Mountain Vault Zagreb"
    project.backup_destinations.append(d)

    path = tmp_path / "inventory.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].serial_number == "SN12345"
    assert loaded.project.servers[0].hypervisor_vendor == "Nutanix AHV"
    assert loaded.project.backup_destinations[0].location == "Iron Mountain Vault Zagreb"


def test_old_clsz_file_without_new_fields_defaults_gracefully(tmp_path):
    project = ClusterProject(name="Pre-inventory-fields")
    project.servers.append(Server.create_default())
    project.backup_destinations.append(BackupDestination.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    for field in ("serial_number", "bmc_ip", "hypervisor_vendor", "hypervisor_version"):
        del raw["servers"][0][field]
    del raw["backup_destinations"][0]["location"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.servers[0].serial_number == ""
    assert loaded.project.servers[0].hypervisor_vendor == ""
    assert loaded.project.backup_destinations[0].location == ""


def test_server_disk_calculator_fields_default_to_zero():
    s = Server.create_default()
    assert s.local_disk_count == 0
    assert s.local_disk_size_tb == 0.0


def test_server_disk_calculator_csv_round_trip(tmp_path):
    s = Server.create_default()
    s.local_disk_count = 12
    s.local_disk_size_tb = 1.09
    path = tmp_path / "servers.csv"
    csv_io.export_servers(path, [s])
    loaded = csv_io.import_servers(path)
    assert loaded[0].local_disk_count == 12
    assert abs(loaded[0].local_disk_size_tb - 1.09) < 0.001
