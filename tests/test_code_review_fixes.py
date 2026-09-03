"""Tests for a batch of real, current defects found by an external code
review (comparing two independent LLM analyses of this codebase). Every
issue below was confirmed still present and fixed here - not stale
findings from an old snapshot.
"""

import copy

from src.calculations.thresholds import Thresholds
from src.models.backup_destination import BackupDestination
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.network_connection import NetworkConnection
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.services.project_service import ProjectService

# ----------------------------------------------------------------------
# comparison.py - was a guaranteed crash the moment Compare was opened
# ----------------------------------------------------------------------

def test_comparison_does_not_crash_on_default_two_site_project():
    from src.calculations.comparison import build_comparison_rows

    project = ClusterProject()
    project.servers.append(Server.create_default())

    rows = build_comparison_rows(project, None, Thresholds())

    assert len(rows) > 0


def test_comparison_does_not_crash_with_a_scenario_b():
    from src.calculations.comparison import build_comparison_rows

    a = ClusterProject()
    a.servers.append(Server.create_default())
    b = ClusterProject()
    b.servers.append(Server.create_default())

    rows = build_comparison_rows(a, b, Thresholds())

    assert all(len(row) == 3 for row in rows)


def test_comparison_handles_a_primary_only_project_with_no_dr():
    from src.calculations.comparison import build_comparison_rows

    project = ClusterProject()
    project.remove_site(DR)
    project.servers.append(Server.create_default())

    rows = build_comparison_rows(project, None, Thresholds())

    assert len(rows) > 0


def test_comparison_dr_readiness_uses_correct_failover_report_fields():
    from src.calculations.comparison import build_comparison_rows

    project = ClusterProject()
    project.servers.append(Server.create_default())
    dr_server = Server.create_default()
    dr_server.site = DR
    project.servers.append(dr_server)
    vm = VirtualMachine.create_default()
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 4
    project.failover_assignments.append(assignment)

    rows = build_comparison_rows(project, None, Thresholds())

    protected_row = next(r for r in rows if r[0] == "DR-protected VMs")
    assert protected_row[1] == "1"


def test_comparison_delta_storage_includes_every_site_not_just_primary_dr():
    from src.calculations.comparison import build_delta_summary

    a = ClusterProject()
    a.add_site("DR2")
    b = ClusterProject()
    b.add_site("DR2")
    storage = Storage.create_default()
    storage.site = "DR2"
    storage.usable_capacity_tb = 10.0
    b.storages.append(storage)

    deltas = build_delta_summary(a, b)

    storage_delta = next(d for label, d in deltas if "Storage" in label)
    assert storage_delta == "+10.0"


# ----------------------------------------------------------------------
# docx_report.py - hardcoded (PRIMARY, DR) dropped DR2/DR3 sections
# ----------------------------------------------------------------------

def test_docx_report_includes_a_third_site():
    from src.calculations.docx_report import build_docx_report

    project = ClusterProject()
    project.add_site("DR2")
    s1 = Server.create_default()
    s1.site = PRIMARY
    s2 = Server.create_default()
    s2.site = "DR2"
    project.servers.extend([s1, s2])

    doc = build_docx_report(project, Thresholds(), app_version="test")

    found = any(
        row.cells[0].text == "DR2"
        for table in doc.tables
        for row in table.rows
    )
    assert found


# ----------------------------------------------------------------------
# _emit_everything_changed - undo/redo previously skipped 3 signals
# ----------------------------------------------------------------------

def test_undo_fires_clusters_backup_and_pricing_signals():
    from src.models.cluster import Cluster

    service = ProjectService()
    service.add_cluster(Cluster.create_default(0))
    fired = {"clusters": False, "backup": False, "pricing": False}
    service.clusters_changed.connect(lambda: fired.__setitem__("clusters", True))
    service.backup_changed.connect(lambda: fired.__setitem__("backup", True))
    service.pricing_changed.connect(lambda: fired.__setitem__("pricing", True))

    service.undo()

    assert all(fired.values())


def test_redo_fires_clusters_backup_and_pricing_signals():
    from src.models.cluster import Cluster

    service = ProjectService()
    service.add_cluster(Cluster.create_default(0))
    service.undo()
    fired = {"clusters": False, "backup": False, "pricing": False}
    service.clusters_changed.connect(lambda: fired.__setitem__("clusters", True))
    service.backup_changed.connect(lambda: fired.__setitem__("backup", True))
    service.pricing_changed.connect(lambda: fired.__setitem__("pricing", True))

    service.redo()

    assert all(fired.values())


# ----------------------------------------------------------------------
# remove_* methods - id() matching silently failed on non-identical
# object references (e.g. a deep copy from an undo snapshot)
# ----------------------------------------------------------------------

def test_remove_servers_works_with_a_deep_copied_reference():
    service = ProjectService()
    service.add_server(Server.create_default())
    stale_copy = copy.deepcopy(service.project.servers[0])
    assert id(stale_copy) != id(service.project.servers[0])

    service.remove_servers([stale_copy])

    assert service.project.servers == []


def test_remove_storages_works_with_a_deep_copied_reference():
    service = ProjectService()
    service.add_storage(Storage.create_default())
    stale_copy = copy.deepcopy(service.project.storages[0])

    service.remove_storages([stale_copy])

    assert service.project.storages == []


def test_remove_backup_destinations_works_with_a_deep_copied_reference():
    service = ProjectService()
    dest = BackupDestination.create_default()
    service.add_backup_destination(dest)
    stale_copy = copy.deepcopy(service.project.backup_destinations[0])

    service.remove_backup_destinations([stale_copy])

    assert service.project.backup_destinations == []


def test_remove_maintenance_items_works_with_a_deep_copied_reference():
    from src.models.maintenance_item import MaintenanceItem

    service = ProjectService()
    item = MaintenanceItem.create_default()
    service.add_maintenance_item(item)
    stale_copy = copy.deepcopy(service.project.maintenance_items[0])

    service.remove_maintenance_items([stale_copy])

    assert service.project.maintenance_items == []


def test_remove_vms_works_with_a_deep_copied_reference():
    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())
    stale_copy = copy.deepcopy(service.project.vms[0])

    service.remove_vms([stale_copy])

    assert service.project.vms == []


def test_remove_connections_works_with_a_deep_copied_reference():
    service = ProjectService()
    conn = NetworkConnection.create_default()
    service.project.connections.append(conn)
    stale_copy = copy.deepcopy(conn)

    service.remove_connections([stale_copy])

    assert service.project.connections == []


# ----------------------------------------------------------------------
# import_engine.py - hardcoded ("Primary", "DR") silently overrode DR2
# ----------------------------------------------------------------------

def test_convert_rows_respects_dr2_when_valid_sites_given():
    from src.models.import_profile import ColumnMapping, ImportProfile
    from src.persistence.import_engine import convert_rows

    profile = ImportProfile(
        name="test",
        mappings=[
            ColumnMapping("name", "Name"),
            ColumnMapping("vcpu", "CPUs"),
            ColumnMapping("ram_gb", "Memory", unit="MB"),
            ColumnMapping("disk_gb", "Disk", unit="GB"),
            ColumnMapping("site", "Site"),
        ],
    )
    rows = [{"Name": "vm-1", "CPUs": "4", "Memory": "8192", "Disk": "100", "Site": "DR2"}]

    vms, _ = convert_rows(rows, profile, site="Primary", valid_sites=["Primary", "DR", "DR2"])

    assert vms[0].site == "DR2"


def test_convert_rows_falls_back_for_a_genuinely_unknown_site():
    from src.models.import_profile import ColumnMapping, ImportProfile
    from src.persistence.import_engine import convert_rows

    profile = ImportProfile(
        name="test",
        mappings=[
            ColumnMapping("name", "Name"),
            ColumnMapping("vcpu", "CPUs"),
            ColumnMapping("ram_gb", "Memory", unit="MB"),
            ColumnMapping("disk_gb", "Disk", unit="GB"),
            ColumnMapping("site", "Site"),
        ],
    )
    rows = [{"Name": "vm-1", "CPUs": "4", "Memory": "8192", "Disk": "100", "Site": "TotallyMadeUp"}]

    vms, _ = convert_rows(rows, profile, site="Primary", valid_sites=["Primary", "DR", "DR2"])

    assert vms[0].site == "Primary"


# ----------------------------------------------------------------------
# csv_io.py - two defaults that silently inflated capacity
# ----------------------------------------------------------------------

def test_csv_import_ht_defaults_off_when_column_missing(tmp_path):
    from src.persistence import csv_io

    path = tmp_path / "servers.csv"
    path.write_text("name,site,sockets,cores_per_socket\nsrv-1,Primary,2,16\n", encoding="utf-8")

    servers = csv_io.import_servers(path)

    assert servers[0].hyperthreading_enabled is False


def test_csv_import_enabled_defaults_off_when_column_missing(tmp_path):
    from src.persistence import csv_io

    path = tmp_path / "servers.csv"
    path.write_text("name,site,sockets,cores_per_socket\nsrv-1,Primary,2,16\n", encoding="utf-8")

    servers = csv_io.import_servers(path)

    assert servers[0].enabled is False


def test_csv_import_respects_explicit_enabled_value(tmp_path):
    from src.persistence import csv_io

    path = tmp_path / "servers.csv"
    path.write_text(
        "name,site,sockets,cores_per_socket,enabled\nsrv-1,Primary,2,16,True\n", encoding="utf-8",
    )

    servers = csv_io.import_servers(path)

    assert servers[0].enabled is True


# ----------------------------------------------------------------------
# project_repository.py - non-atomic write could corrupt a .clsz on
# a crash mid-write
# ----------------------------------------------------------------------

def test_save_project_normal_round_trip_still_works(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Atomic write test")
    path = tmp_path / "test.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.name == "Atomic write test"


def test_save_project_leaves_no_temp_file_behind(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Test")
    path = tmp_path / "test.clsz"

    project_repository.save_project(project, path, Thresholds())

    leftovers = list(tmp_path.glob(".test.clsz.*.tmp"))
    assert leftovers == []


def test_save_project_preserves_original_file_if_write_fails(tmp_path, monkeypatch):
    import json

    from src.persistence import project_repository

    project = ClusterProject(name="Original")
    path = tmp_path / "test.clsz"
    project_repository.save_project(project, path, Thresholds())
    original_content = path.read_text(encoding="utf-8")

    monkeypatch.setattr(json, "dumps", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        project_repository.save_project(project, path, Thresholds())
    except RuntimeError:
        pass

    assert path.read_text(encoding="utf-8") == original_content
    leftovers = list(tmp_path.glob(".test.clsz.*.tmp"))
    assert leftovers == []


# ----------------------------------------------------------------------
# VMs page - "CPU Oversub." card silently only showed Primary
# ----------------------------------------------------------------------

def test_cpu_oversub_card_label_names_the_site():
    import pytest
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    page = VirtualMachinesPage(service)

    assert page.card_cpu_ratio.title_label.text() == "CPU Oversub. (Primary)"
