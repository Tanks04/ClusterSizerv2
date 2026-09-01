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


def test_acknowledge_action_confirms_selected_assignment():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    vm.vcpu = 8
    service.add_vm(vm)
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    a.vcpu = 16
    service.add_failover_assignment(a)

    page.failover_table.selectRow(0)
    page._set_failover_confirmed_for_selected(True)

    assert service.project.failover_assignments[0].footprint_confirmed is True


def test_un_acknowledge_action_reverts_confirmation():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    vm = VirtualMachine.create_default()
    service.add_vm(vm)
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    service.add_failover_assignment(a)
    service.set_failover_assignment_confirmed([a], True)

    page.failover_table.selectRow(0)  # refresh() from the confirm call reset selection
    page._set_failover_confirmed_for_selected(False)

    assert service.project.failover_assignments[0].footprint_confirmed is False


def test_acknowledge_with_no_selection_shows_a_message(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    service = ProjectService()
    page = VirtualMachinesPage(service)

    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))

    page._set_failover_confirmed_for_selected(True)

    assert informed.get("called") is True


def test_assign_selected_to_failover_creates_one_assignment_per_vm(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    service = ProjectService()
    vm1 = VirtualMachine.create_default()
    vm1.vcpu = 8
    vm1.ram_gb = 32
    vm1.disk_gb = 500
    vm2 = VirtualMachine.create_default()
    vm2.vcpu = 4
    vm2.ram_gb = 16
    vm2.disk_gb = 200
    service.add_vm(vm1)
    service.add_vm(vm2)
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._assign_selected_to_failover("DR")

    assert len(service.project.failover_assignments) == 2
    assignments_by_vm = {a.vm_uid: a for a in service.project.failover_assignments}
    assert assignments_by_vm[vm1.uid].vcpu == 8
    assert assignments_by_vm[vm1.uid].ram_gb == 32
    assert assignments_by_vm[vm1.uid].disk_gb == 500
    assert assignments_by_vm[vm2.uid].target_site == "DR"


def test_assign_selected_to_failover_is_one_undo_step(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())
    service.add_vm(VirtualMachine.create_default())
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._assign_selected_to_failover("DR")
    assert len(service.project.failover_assignments) == 2

    service.undo()
    assert service.project.failover_assignments == []


def test_assign_selected_to_failover_with_no_selection_does_nothing():
    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())
    page = VirtualMachinesPage(service)

    page._assign_selected_to_failover("DR")

    assert service.project.failover_assignments == []


def test_custom_actions_include_assign_to_failover_per_site():
    service = ProjectService()
    service.project.add_site("DR2")
    page = VirtualMachinesPage(service)

    labels = [label for label, _ in page.table._custom_actions]

    assert any("Assign to Failover (DR2)" in l for l in labels)
    assert any("Assign to Failover (Primary)" in l for l in labels)
