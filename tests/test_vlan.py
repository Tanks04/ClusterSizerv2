from src.calculations.thresholds import Thresholds
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan
from src.persistence import csv_io, project_repository


def test_create_default():
    vlan = Vlan.create_default()
    assert vlan.site == PRIMARY
    assert vlan.name == ""
    assert vlan.uid


def test_vlan_csv_round_trip(tmp_path):
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    vlan.site = DR
    vlan.network = "192.168.10.0/24"
    vlan.gateway = "192.168.10.1"
    vlan.notes = "Perimeter segment"

    path = tmp_path / "vlans.csv"
    csv_io.export_vlans(path, [vlan])
    loaded = csv_io.import_vlans(path)

    assert len(loaded) == 1
    assert loaded[0].name == "DMZ"
    assert loaded[0].site == DR
    assert loaded[0].network == "192.168.10.0/24"
    assert loaded[0].gateway == "192.168.10.1"
    assert loaded[0].notes == "Perimeter segment"


def test_vlan_csv_import_defaults_missing_site_to_primary(tmp_path):
    path = tmp_path / "vlans.csv"
    path.write_text("name,site,network,gateway,notes\nDMZ,,,,\n", encoding="utf-8")

    loaded = csv_io.import_vlans(path)

    assert loaded[0].site == PRIMARY


def test_vlan_and_vm_reference_round_trip_via_clsz(tmp_path):
    project = ClusterProject(name="VLAN test")
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    project.vlans.append(vlan)

    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid
    project.vms.append(vm)

    path = tmp_path / "vlan.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.vlans[0].name == "DMZ"
    assert loaded.project.vms[0].vlan_uid == loaded.project.vlans[0].uid


def test_old_clsz_file_without_vlans_defaults_to_empty(tmp_path):
    project = ClusterProject(name="Pre-VLAN")
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["vlans"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.vlans == []


def test_vm_field_vlan_uid_not_in_csv_schema():
    """Deliberately excluded from the flat VM CSV schema - same
    precedent as StorageShelf/hci_server_uids - a re-imported VLANs CSV
    generates fresh UIDs, so a stored cross-reference would go stale."""
    assert "vlan_uid" not in csv_io.VM_FIELDS
