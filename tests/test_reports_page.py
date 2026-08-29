"""Real Qt tests for ReportsPage's text report generation - this had NO
test coverage at all until a real bug was found from it: the v4.0.0
multi-site refactor changed build_reports() from a fixed 3-tuple to a
dict keyed by site name, but reports_page.py was never updated to
match, so opening the Reports tab (or loading any second project while
Reports had already been constructed) crashed with ValueError/
AttributeError - completely undetected through every release since."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.gui.pages.reports_page import ReportsPage
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_report_generates_for_an_empty_project_without_crashing():
    service = ProjectService()
    page = ReportsPage(service)

    text = page.text_area.toPlainText()

    assert "Primary" in text or "PRIMARY" in text
    assert "DR" in text


def test_report_includes_a_third_site():
    service = ProjectService()
    service.project.add_site("DR2")
    server = Server.create_default()
    server.site = "DR2"
    service.add_server(server)

    page = ReportsPage(service)
    text = page.text_area.toPlainText()

    assert "[DR2]" in text


def test_report_reflects_actual_vm_and_server_counts():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    service.add_server(server)
    vm = VirtualMachine.create_default()
    vm.site = "Primary"
    service.add_vm(vm)

    page = ReportsPage(service)
    text = page.text_area.toPlainText()

    assert "Servers            : 1" in text
    assert "VM count            : 1" in text


def test_switching_projects_does_not_crash_the_already_open_reports_page():
    """The exact scenario reported directly: load one project, then
    load a different one while Reports has already been constructed -
    must not raise."""
    service = ProjectService()
    page = ReportsPage(service)

    service.new_project()  # simulates loading a different/blank project
    text_after = page.text_area.toPlainText()

    assert "Primary" in text_after or "PRIMARY" in text_after


def test_report_includes_failover_assignment_data():
    from src.models.failover_assignment import FailoverAssignment

    service = ProjectService()
    vm = VirtualMachine.create_default()
    vm.vcpu = 4
    vm.ram_gb = 16
    vm.disk_gb = 100
    service.add_vm(vm)
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    a.vcpu = 4
    a.ram_gb = 16
    a.disk_gb = 100
    service.add_failover_assignment(a)

    page = ReportsPage(service)
    text = page.text_area.toPlainText()

    assert "Failover Assigned VMs: 1" in text
