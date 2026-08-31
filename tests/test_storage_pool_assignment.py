"""Tests for the Storage disk-count/size calculator fields and VM-to-
specific-storage-pool assignment (VirtualMachine.storage_uid) - the
three-part storage redesign requested directly: disk count x size auto
-calculates raw capacity, usable stays a manual real number, and a VM
can be assigned to a SPECIFIC storage entity rather than only counting
toward a site-wide aggregate."""

from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.persistence import csv_io, project_repository
from src.models.cluster_project import ClusterProject
from src.calculations.thresholds import Thresholds


def test_storage_disk_calculator_fields_default_to_zero():
    s = Storage.create_default()
    assert s.disk_count == 0
    assert s.disk_size_tb == 0.0


def test_storage_disk_calculator_csv_round_trip(tmp_path):
    s = Storage.create_default()
    s.disk_count = 24
    s.disk_size_tb = 2.0
    path = tmp_path / "storage.csv"
    csv_io.export_storages(path, [s])
    loaded = csv_io.import_storages(path)
    assert loaded[0].disk_count == 24
    assert loaded[0].disk_size_tb == 2.0


def test_vm_storage_uid_defaults_to_empty():
    vm = VirtualMachine.create_default()
    assert vm.storage_uid == ""


def test_vm_storage_uid_not_in_csv_schema():
    """Deliberately excluded, same precedent as vlan_uid - a
    re-imported Storage CSV generates fresh UIDs, so a stored
    cross-reference would go stale immediately."""
    assert "storage_uid" not in csv_io.VM_FIELDS


def test_vm_storage_uid_clsz_round_trip(tmp_path):
    project = ClusterProject(name="Storage pool test")
    storage = Storage.create_default()
    storage.disk_count = 12
    storage.disk_size_tb = 1.09
    project.storages.append(storage)
    vm = VirtualMachine.create_default()
    vm.storage_uid = storage.uid
    project.vms.append(vm)

    path = tmp_path / "pool.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].disk_count == 12
    assert loaded.project.vms[0].storage_uid == loaded.project.storages[0].uid


def test_old_clsz_file_without_new_fields_defaults_gracefully(tmp_path):
    project = ClusterProject(name="Pre-pool-assignment")
    project.storages.append(Storage.create_default())
    project.vms.append(VirtualMachine.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["storages"][0]["disk_count"]
    del raw["storages"][0]["disk_size_tb"]
    del raw["vms"][0]["storage_uid"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].disk_count == 0
    assert loaded.project.vms[0].storage_uid == ""
