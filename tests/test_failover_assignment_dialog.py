"""Real Qt tests for FailoverAssignmentDialog."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.failover_assignment_dialog import FailoverAssignmentDialog
from src.models.failover_assignment import FailoverAssignment
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _vm(name, vcpu=2, ram_gb=8.0, disk_gb=100.0):
    vm = VirtualMachine.create_default()
    vm.name = name
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    vm.disk_gb = disk_gb
    return vm


def test_new_assignment_defaults_footprint_to_first_vm():
    vm = _vm("erp-db01", vcpu=4, ram_gb=16.0, disk_gb=200.0)
    dialog = FailoverAssignmentDialog(vms=[vm], sites=["Primary", "DR"])

    assert dialog.vcpu_spin.value() == 4
    assert dialog.ram_spin.value() == 16.0
    assert dialog.disk_spin.value() == 200.0


def test_switching_vm_resyncs_footprint_defaults():
    vm1 = _vm("vm1", vcpu=4, ram_gb=16.0, disk_gb=200.0)
    vm2 = _vm("vm2", vcpu=2, ram_gb=8.0, disk_gb=50.0)
    dialog = FailoverAssignmentDialog(vms=[vm1, vm2], sites=["Primary", "DR"])

    dialog.vm_combo.setCurrentIndex(1)

    assert dialog.vcpu_spin.value() == 2
    assert dialog.ram_spin.value() == 8.0


def test_get_assignment_reflects_entered_fields():
    vm = _vm("erp-db01")
    dialog = FailoverAssignmentDialog(vms=[vm], sites=["Primary", "DR", "DR2"])

    dialog.target_site_combo.setCurrentText("DR2")
    dialog.vcpu_spin.setValue(1)

    assignment = dialog.get_assignment()

    assert assignment.vm_uid == vm.uid
    assert assignment.target_site == "DR2"
    assert assignment.vcpu == 1


def test_editing_an_existing_assignment_preloads_its_fields():
    vm = _vm("erp-db01")
    existing = FailoverAssignment.create_default()
    existing.vm_uid = vm.uid
    existing.target_site = "DR"
    existing.vcpu = 2
    existing.ram_gb = 8.0
    existing.disk_gb = 100.0

    dialog = FailoverAssignmentDialog(existing, vms=[vm], sites=["Primary", "DR"])

    assert dialog.vm_combo.currentData() == vm.uid
    assert dialog.target_site_combo.currentText() == "DR"
    assert dialog.vcpu_spin.value() == 2


def test_editing_preserves_the_original_uid():
    vm = _vm("erp-db01")
    existing = FailoverAssignment.create_default()
    existing.vm_uid = vm.uid
    existing.target_site = "DR"

    dialog = FailoverAssignmentDialog(existing, vms=[vm], sites=["Primary", "DR"])
    dialog.vcpu_spin.setValue(99)

    result = dialog.get_assignment()

    assert result.uid == existing.uid
