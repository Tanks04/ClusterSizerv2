import pytest

pytest.importorskip("docx")

from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.calculations.thresholds import Thresholds
from src.calculations.docx_report import build_docx_report


def _build_sample_project() -> ClusterProject:
    project = ClusterProject(name="Test Project")

    s1 = Server.create_default()
    s1.name = "esxi-p01"
    s1.site = PRIMARY
    project.servers.append(s1)

    st1 = Storage.create_default()
    st1.name = "san-p01"
    st1.site = PRIMARY
    project.storages.append(st1)

    sw1 = NetworkSwitch.create_default()
    sw1.name = "sw-p01"
    sw1.site = PRIMARY
    project.switches.append(sw1)

    conn = NetworkConnection.create_default()
    conn.server_uid = s1.uid
    conn.switch_uid = sw1.uid
    project.connections.append(conn)

    vm = VirtualMachine.create_default()
    vm.name = "app01"
    vm.site = PRIMARY
    project.vms.append(vm)

    return project


def test_build_docx_report_has_all_expected_sections():
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds(), app_version="9.9.9")

    headings = [p.text for p in document.paragraphs if p.style.name.startswith("Heading") or p.style.name == "Title"]

    assert "Test Project" in headings
    assert "Servers" in headings
    assert "Storage" in headings
    assert "Network" in headings
    assert "Cluster" in headings
    assert "Pricing" in headings
    assert "Virtual Machines" in headings


def test_build_docx_report_includes_version_and_project_name():
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds(), app_version="9.9.9")

    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "9.9.9" in all_text
    assert "Test Project" in all_text


def test_build_docx_report_server_table_has_expected_row_count():
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds())

    # First table is the per-site summary (2 rows: Primary + DR), second
    # is the full server listing (1 header + 1 data row for our single server)
    server_detail_table = document.tables[1]
    assert len(server_detail_table.rows) == 2  # header + 1 server
    assert server_detail_table.rows[1].cells[0].text == "esxi-p01"


def test_build_docx_report_empty_project_does_not_crash():
    project = ClusterProject(name="Empty")
    document = build_docx_report(project, Thresholds())
    assert document is not None


def test_pricing_section_shows_equipment_total():
    project = _build_sample_project()
    project.servers[0].price = 15000.0

    document = build_docx_report(project, Thresholds())

    all_text = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "15,000.00" in all_text


def test_pricing_section_lists_maintenance_items():
    from src.models.maintenance_item import MaintenanceItem

    project = _build_sample_project()
    project.maintenance_items.append(MaintenanceItem(
        uid="x", name="Firewall subscription", category="Subscription",
        cost=1200.0, duration_months=12, expiry_date="2027-01-01",
    ))

    document = build_docx_report(project, Thresholds())

    headings = [p.text for p in document.paragraphs if p.style.name.startswith("Heading")]
    assert "Licenses, Warranties & Maintenance" in headings

    all_text = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "Firewall subscription" in all_text


def test_pricing_section_with_no_pricing_data_does_not_crash():
    """A project with zero pricing entered anywhere - the section should
    still render (all zeros), not error out or skip itself."""
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds())

    headings = [p.text for p in document.paragraphs if p.style.name.startswith("Heading")]
    assert "Pricing" in headings


def test_build_docx_report_can_be_saved(tmp_path):
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds())
    output_path = tmp_path / "report.docx"
    document.save(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_rack_sizing_shows_numbers_for_on_premise_site():
    from src.models.server import Server
    from src.models.cluster_project import PRIMARY

    project = _build_sample_project()
    server = Server.create_default()
    server.site = PRIMARY
    server.rack_units = 2
    server.power_watts = 500.0
    project.servers.append(server)

    document = build_docx_report(project, Thresholds())
    all_text = "\n".join(p.text for p in document.paragraphs)

    assert "Rack Sizing: 2 U, 500 W" in all_text


def test_rack_sizing_shows_cloud_for_a_cloud_site():
    from src.models.cluster_project import CLOUD

    project = _build_sample_project()
    project.dr_deployment_model = CLOUD

    document = build_docx_report(project, Thresholds())
    all_text = "\n".join(p.text for p in document.paragraphs)

    assert "Rack Sizing: Cloud (not applicable)" in all_text


def test_rack_sizing_shows_used_and_capacity_when_capacity_is_set():
    from src.models.server import Server
    from src.models.cluster_project import PRIMARY

    project = _build_sample_project()
    server = Server.create_default()
    server.site = PRIMARY
    server.rack_units = 12
    server.power_watts = 500.0
    project.servers.append(server)
    project.primary_rack_capacity_u = 84

    document = build_docx_report(project, Thresholds())
    all_text = "\n".join(p.text for p in document.paragraphs)

    assert "12 / 84 U, 500 W" in all_text


def test_rack_sizing_flags_over_capacity():
    from src.models.server import Server
    from src.models.cluster_project import PRIMARY

    project = _build_sample_project()
    server = Server.create_default()
    server.site = PRIMARY
    server.rack_units = 12
    project.servers.append(server)
    project.primary_rack_capacity_u = 10

    document = build_docx_report(project, Thresholds())
    all_text = "\n".join(p.text for p in document.paragraphs)

    assert "over capacity" in all_text
    assert "12 / 10 U" in all_text
