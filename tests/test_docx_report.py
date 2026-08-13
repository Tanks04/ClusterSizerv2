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


def test_build_docx_report_can_be_saved(tmp_path):
    project = _build_sample_project()
    document = build_docx_report(project, Thresholds())
    output_path = tmp_path / "report.docx"
    document.save(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0
