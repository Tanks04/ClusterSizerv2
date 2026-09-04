"""Tests for a batch of Word report changes: row numbers on every
table, the Cluster section converted from a paragraph printout to a
proper table (with empty sites skipped entirely), the VM detail table
gaining every recorded field (only the ones actually filled in, in
landscape), and a VM summary block matching the VMs tab's own cards.
"""

import pytest

from src.calculations.thresholds import Thresholds
from src.models.cluster import Cluster
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.server import Server
from src.models.storage import Storage, StoragePool
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan

docx = pytest.importorskip("docx")
from src.calculations.docx_report import build_docx_report


def _table_text(document) -> str:
    return "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )


# ----------------------------------------------------------------------
# Row numbering on every table
# ----------------------------------------------------------------------

def test_every_table_has_a_row_number_column():
    project = ClusterProject()
    project.servers.append(Server.create_default())

    document = build_docx_report(project, Thresholds(), app_version="test")

    numbered_tables = [t for t in document.tables if t.rows[0].cells[0].text == "#"]
    assert len(numbered_tables) > 0


def test_row_numbers_start_at_one_and_increment():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    project.servers.append(Server.create_default())

    document = build_docx_report(project, Thresholds(), app_version="test")

    server_table = next(t for t in document.tables if t.rows[0].cells[1].text == "Name")
    assert server_table.rows[1].cells[0].text == "1"
    assert server_table.rows[2].cells[0].text == "2"


def test_metric_value_tables_are_not_numbered():
    """The Cluster section's Metric/Value grid isn't a list of items -
    it shouldn't get a meaningless row-number column."""
    project = ClusterProject()
    project.servers.append(Server.create_default())

    document = build_docx_report(project, Thresholds(), app_version="test")

    metric_tables = [t for t in document.tables if t.rows[0].cells[0].text == "Metric"]
    assert len(metric_tables) > 0
    for table in metric_tables:
        assert table.rows[0].cells[0].text == "Metric"  # not "#"


# ----------------------------------------------------------------------
# Cluster section - table format, empty sites skipped
# ----------------------------------------------------------------------

def test_cluster_section_uses_a_table_not_paragraphs():
    project = ClusterProject()
    project.servers.append(Server.create_default())

    document = build_docx_report(project, Thresholds(), app_version="test")

    assert any(
        t.rows[0].cells[0].text == "Metric" and
        any(row.cells[0].text == "Servers" for row in t.rows)
        for t in document.tables
    )


def test_empty_dr_site_shows_a_short_note_not_a_full_table():
    project = ClusterProject()
    server = Server.create_default()
    server.site = PRIMARY
    project.servers.append(server)

    document = build_docx_report(project, Thresholds(), app_version="test")

    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Nothing configured at DR yet." in all_text


def test_non_empty_site_gets_the_full_metrics_table():
    project = ClusterProject()
    server = Server.create_default()
    server.site = DR
    project.servers.append(server)

    document = build_docx_report(project, Thresholds(), app_version="test")

    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Nothing configured at DR yet." not in all_text


# ----------------------------------------------------------------------
# VM detail table - dynamic column filtering
# ----------------------------------------------------------------------

def _vm_table(document):
    return next(t for t in document.tables if "Workload Tier" in [c.text for c in t.rows[0].cells])


def test_core_columns_always_present_even_with_nothing_optional_filled():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm = VirtualMachine.create_default()
    vm.name = "vm-1"
    project.vms.append(vm)

    document = build_docx_report(project, Thresholds(), app_version="test")

    headers = [c.text for c in _vm_table(document).rows[0].cells]
    for expected in ["Name", "Site", "vCPU", "RAM", "Disk", "Power", "Workload Tier"]:
        assert expected in headers


def test_optional_columns_dropped_when_no_vm_has_data():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm = VirtualMachine.create_default()
    project.vms.append(vm)

    document = build_docx_report(project, Thresholds(), app_version="test")

    headers = [c.text for c in _vm_table(document).rows[0].cells]
    for unexpected in ["DR Category", "IP Address", "OS", "VLAN", "Notes", "Cluster"]:
        assert unexpected not in headers


def test_optional_column_kept_when_at_least_one_vm_has_data():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm1 = VirtualMachine.create_default()
    vm1.notes = "Has a note"
    vm2 = VirtualMachine.create_default()
    project.vms.extend([vm1, vm2])

    document = build_docx_report(project, Thresholds(), app_version="test")

    headers = [c.text for c in _vm_table(document).rows[0].cells]
    assert "Notes" in headers
    assert "DR Category" not in headers


def test_vm_without_the_data_still_shows_dash_in_kept_column():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm1 = VirtualMachine.create_default()
    vm1.notes = "Has a note"
    vm2 = VirtualMachine.create_default()  # no notes
    project.vms.extend([vm1, vm2])

    document = build_docx_report(project, Thresholds(), app_version="test")

    table = _vm_table(document)
    headers = [c.text for c in table.rows[0].cells]
    notes_col = headers.index("Notes")
    assert table.rows[2].cells[notes_col].text == "-"


def test_all_optional_columns_kept_when_everything_is_filled():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    cluster = Cluster.create_default(0)
    project.clusters.append(cluster)
    vlan = Vlan.create_default()
    project.vlans.append(vlan)
    vm = VirtualMachine.create_default()
    vm.dr_category = "Tier1"
    vm.ip_address = "10.0.0.1"
    vm.os = "Linux"
    vm.vlan_uid = vlan.uid
    vm.cluster_uid = cluster.uid
    vm.notes = "note"
    project.vms.append(vm)

    document = build_docx_report(project, Thresholds(), app_version="test")

    headers = [c.text for c in _vm_table(document).rows[0].cells]
    for expected in ["DR Category", "IP Address", "OS", "VLAN", "Cluster", "Notes"]:
        assert expected in headers


def test_pinned_server_name_resolved_correctly():
    project = ClusterProject()
    server = Server.create_default()
    server.name = "srvr4"
    project.servers.append(server)
    vm = VirtualMachine.create_default()
    vm.pinned_server_uid = server.uid
    project.vms.append(vm)

    document = build_docx_report(project, Thresholds(), app_version="test")

    assert "srvr4" in _table_text(document)


# ----------------------------------------------------------------------
# Landscape orientation
# ----------------------------------------------------------------------

def test_vms_section_switches_to_landscape():
    project = ClusterProject()
    project.servers.append(Server.create_default())

    document = build_docx_report(project, Thresholds(), app_version="test")

    last_section = document.sections[-1]
    assert last_section.page_width > last_section.page_height


# ----------------------------------------------------------------------
# VM summary block at the bottom
# ----------------------------------------------------------------------

def test_vm_summary_block_present_with_correct_totals():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm1 = VirtualMachine.create_default()
    vm1.vcpu = 8
    vm1.ram_gb = 32
    vm2 = VirtualMachine.create_default()
    vm2.vcpu = 4
    vm2.ram_gb = 16
    project.vms.extend([vm1, vm2])

    document = build_docx_report(project, Thresholds(), app_version="test")

    summary_table = next(
        t for t in document.tables
        if t.rows[0].cells[0].text == "Metric"
        and any("vCPU Demand" in row.cells[0].text for row in t.rows)
    )
    rows = {row.cells[0].text: row.cells[1].text for row in summary_table.rows[1:]}
    assert rows["VMs"] == "2"
    assert rows["vCPU Demand (Powered On)"] == "12"
    assert rows["RAM Demand (Powered On)"] == "48 GB"


def test_vm_summary_excludes_powered_off_vms_from_demand():
    project = ClusterProject()
    project.servers.append(Server.create_default())
    vm1 = VirtualMachine.create_default()
    vm1.vcpu = 8
    vm2 = VirtualMachine.create_default()
    vm2.vcpu = 4
    vm2.powered_on = False
    project.vms.extend([vm1, vm2])

    document = build_docx_report(project, Thresholds(), app_version="test")

    summary_table = next(
        t for t in document.tables
        if t.rows[0].cells[0].text == "Metric"
        and any("vCPU Demand" in row.cells[0].text for row in t.rows)
    )
    rows = {row.cells[0].text: row.cells[1].text for row in summary_table.rows[1:]}
    assert rows["VMs"] == "2"  # total count includes disabled
    assert rows["vCPU Demand (Powered On)"] == "8"  # demand excludes it
