"""Real Qt integration tests for the Failover Assignments section of
VirtualMachinesPage."""

import pytest

pytest.importorskip("PySide6")

from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.project_service import ProjectService
from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.models.virtual_machine import VirtualMachine
from src.models.failover_assignment import FailoverAssignment


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_failover_table_empty_initially():
    service = ProjectService()
    page = VirtualMachinesPage(service)

    assert page.failover_model.rowCount() == 0


def test_adding_assignment_via_service_refreshes_the_table():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    vm.name = "erp-db01"
    service.add_vm(vm)

    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    service.add_failover_assignment(a)

    assert page.failover_model.rowCount() == 1


def test_bulk_toggle_and_table_agree():
    """The bulk checkbox+combo UI and the standalone table operate on
    the same underlying list - a bulk assignment should show up in
    the table without any extra wiring."""
    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    vm.vcpu = 4
    vm.ram_gb = 16
    vm.disk_gb = 100
    service.add_vm(vm)

    page.table.selectRow(0)
    page.bulk_failover_site_combo.setCurrentText("DR")
    page.bulk_failover_check.setChecked(True)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_failover_for_selected_from_checkbox()

    assert page.failover_model.rowCount() == 1
    assert page.failover_model.assignment_at(0).target_site == "DR"


def test_deleting_a_vm_removes_its_row_from_the_failover_table():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    service.add_vm(vm)
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    service.add_failover_assignment(a)
    assert page.failover_model.rowCount() == 1

    service.remove_vms([vm])

    assert page.failover_model.rowCount() == 0


def test_add_failover_assignment_via_dialog(monkeypatch):
    from src.gui.dialogs.failover_assignment_dialog import FailoverAssignmentDialog

    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    vm.name = "erp-db01"
    service.add_vm(vm)

    monkeypatch.setattr(FailoverAssignmentDialog, "exec", lambda self: True)

    page._add_failover_assignment()

    assert page.failover_model.rowCount() == 1
    assert page.failover_model.assignment_at(0).vm_uid == vm.uid
