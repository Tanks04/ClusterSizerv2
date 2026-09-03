"""Real Qt tests for FailoverAssignmentTableModel."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.models.failover_assignment_table_model import FailoverAssignmentTableModel
from src.models.failover_assignment import FailoverAssignment
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _data(model, row, col):
    return model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole)


def test_basic_fields():
    vm = VirtualMachine.create_default()
    vm.name = "erp-db01"
    vm.vcpu = 4
    vm.ram_gb = 16.0
    vm.disk_gb = 200.0
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = "DR"
    a.vcpu = 4
    a.ram_gb = 16.0
    a.disk_gb = 200.0

    model = FailoverAssignmentTableModel([a], vms_provider=lambda: [vm])

    assert _data(model, 0, 0) == "erp-db01"
    assert _data(model, 0, 1) == "DR"
    assert _data(model, 0, 2) == "4"
    assert _data(model, 0, 3) == "16.0"
    assert _data(model, 0, 4) == "200.0"


def test_deleted_vm_shows_placeholder_not_crash():
    a = FailoverAssignment.create_default()
    a.vm_uid = "some-deleted-uid"
    a.target_site = "DR"

    model = FailoverAssignmentTableModel([a], vms_provider=lambda: [])

    assert _data(model, 0, 0) == "(deleted VM)"


def test_same_vm_can_appear_in_multiple_rows_for_different_sites():
    vm = VirtualMachine.create_default()
    vm.name = "erp-db01"
    a1 = FailoverAssignment.create_default()
    a1.vm_uid = vm.uid; a1.target_site = "DR"; a1.vcpu = 4
    a2 = FailoverAssignment.create_default()
    a2.vm_uid = vm.uid; a2.target_site = "DR2"; a2.vcpu = 2

    model = FailoverAssignmentTableModel([a1, a2], vms_provider=lambda: [vm])

    assert model.rowCount() == 2
    assert _data(model, 0, 1) == "DR"
    assert _data(model, 1, 1) == "DR2"
    assert _data(model, 0, 0) == _data(model, 1, 0) == "erp-db01"


def test_set_assignments_resets_the_model():
    model = FailoverAssignmentTableModel()
    assert model.rowCount() == 0

    a = FailoverAssignment.create_default()
    model.set_assignments([a])

    assert model.rowCount() == 1
    assert model.assignment_at(0) is a


def test_stale_marker_and_color_shown_for_exceeding_field():
    vm = VirtualMachine.create_default()
    vm.vcpu = 8; vm.ram_gb = 32; vm.disk_gb = 500
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid; a.target_site = "DR"
    a.vcpu = 16; a.ram_gb = 32; a.disk_gb = 500  # only vCPU exceeds

    model = FailoverAssignmentTableModel([a], vms_provider=lambda: [vm])

    vcpu_text = _data(model, 0, 2)
    ram_text = _data(model, 0, 3)
    assert "\u26a0" in vcpu_text
    assert "\u26a0" not in ram_text
    assert model.data(model.index(0, 2), Qt.ItemDataRole.ForegroundRole) is not None
    assert model.data(model.index(0, 3), Qt.ItemDataRole.ForegroundRole) is None


def test_confirmed_assignment_shows_no_marker_even_if_exceeding():
    vm = VirtualMachine.create_default()
    vm.vcpu = 8
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid; a.target_site = "DR"
    a.vcpu = 16
    a.footprint_confirmed = True

    model = FailoverAssignmentTableModel([a], vms_provider=lambda: [vm])

    assert "\u26a0" not in _data(model, 0, 2)
    assert model.data(model.index(0, 2), Qt.ItemDataRole.ForegroundRole) is None
