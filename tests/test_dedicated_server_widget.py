"""Tests for the "Dedicated Server Loads" section on Summary - one
2-line block per server with VMs pinned directly to it (as opposed to
floating at the Cluster level), matching the exact format requested:
"srvr4 has dedicated VMs" / "4x VM's, ... CPU-OS: X:1 RAM-UTIL: Y%".
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _server_with_pinned_vms(vm_count=4, vcpu_each=21, ram_each=113 / 4, disk_each=450 / 4):
    project = ClusterProject()
    server = Server.create_default()
    server.name = "srvr4"
    server.sockets = 2
    server.cores_per_socket = 16
    server.ram_gb = 512
    server.hyperthreading_enabled = False
    project.servers.append(server)
    for _ in range(vm_count):
        vm = VirtualMachine.create_default()
        vm.vcpu = vcpu_each
        vm.ram_gb = ram_each
        vm.disk_gb = disk_each
        vm.pinned_server_uid = server.uid
        project.vms.append(vm)
    return project, server


def test_widget_hidden_when_no_pinned_vms():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project = ClusterProject()
    project.servers.append(Server.create_default())
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    assert widget.isVisible() is False


def test_widget_shown_when_a_server_has_pinned_vms():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    assert widget.isVisible() is True


def test_widget_shows_server_specs_in_header():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    header_text = widget._labels[0].text()
    assert "srvr4" in header_text
    assert "2x16c" in header_text
    assert "512" in header_text


def test_widget_shows_vm_count_and_demand_in_detail_line():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    detail_text = widget._labels[1].text()
    assert "4x VM's" in detail_text
    assert "113 GB RAM" in detail_text
    assert "450 GB disk" in detail_text
    assert "CPU-OS" in detail_text
    assert "RAM-UTIL" in detail_text


def test_widget_ratio_values_match_the_calculation_layer():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    detail_text = widget._labels[1].text()
    expected_cpu = project.server_cpu_ratio(server)
    expected_ram = project.server_ram_ratio(server)
    assert f"{expected_cpu:.1f}:1" in detail_text
    assert f"{expected_ram * 100:.0f}%" in detail_text


def test_widget_shows_one_block_per_pinned_server():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project = ClusterProject()
    srv1 = Server.create_default()
    srv1.name = "srv-a"
    srv2 = Server.create_default()
    srv2.name = "srv-b"
    project.servers.extend([srv1, srv2])
    for srv in (srv1, srv2):
        vm = VirtualMachine.create_default()
        vm.pinned_server_uid = srv.uid
        project.vms.append(vm)
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    all_text = " ".join(l.text() for l in widget._labels)
    assert "srv-a" in all_text
    assert "srv-b" in all_text


def test_widget_only_lists_servers_with_pinned_vms_not_every_server():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    plain_server = Server.create_default()
    plain_server.name = "no-pins-here"
    project.servers.append(plain_server)
    widget = DedicatedServerWidget()

    widget.set_data(project, Thresholds())

    all_text = " ".join(l.text() for l in widget._labels)
    assert "no-pins-here" not in all_text


def test_widget_refreshes_when_data_changes():
    from src.gui.widgets.dedicated_server_widget import DedicatedServerWidget

    project, server = _server_with_pinned_vms()
    widget = DedicatedServerWidget()
    widget.set_data(project, Thresholds())
    assert widget.isVisible() is True

    for vm in project.vms:
        vm.pinned_server_uid = ""
    widget.set_data(project, Thresholds())

    assert widget.isVisible() is False


# ----------------------------------------------------------------------
# Summary page integration
# ----------------------------------------------------------------------

def test_summary_page_has_the_widget_and_updates_it_on_refresh():
    from src.gui.pages.summary_page import SummaryPage
    from src.services.project_service import ProjectService

    service = ProjectService()
    srv = Server.create_default()
    srv.name = "srvr4"
    service.add_server(srv)
    vm = VirtualMachine.create_default()
    vm.pinned_server_uid = srv.uid
    service.add_vm(vm)

    page = SummaryPage(service)
    page.show()
    QApplication.processEvents()

    assert page.dedicated_server_widget.isVisible() is True
