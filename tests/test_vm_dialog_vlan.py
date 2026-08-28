"""Real Qt tests for VMDialog's VLAN dropdown - deliberately independent
of IP Address, per direct request (assigning a VLAN never requires
also entering an IP)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.vm_dialog import VMDialog
from src.models.vlan import Vlan
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_no_vlans_available_shows_only_none_option():
    dialog = VMDialog()
    assert dialog.vlan_combo.count() == 1
    assert dialog.vlan_combo.currentText() == "(none)"


def test_new_vm_defaults_to_no_vlan():
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    dialog = VMDialog(vlans=[vlan])

    vm = dialog.get_vm()

    assert vm.vlan_uid == ""


def test_selecting_a_vlan_sets_vlan_uid():
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    dialog = VMDialog(vlans=[vlan])

    dialog.vlan_combo.setCurrentIndex(1)  # index 0 is "(none)"
    vm = dialog.get_vm()

    assert vm.vlan_uid == vlan.uid


def test_vlan_assignment_does_not_require_an_ip_address():
    vlan = Vlan.create_default()
    dialog = VMDialog(vlans=[vlan])
    dialog.vlan_combo.setCurrentIndex(1)
    # ip_address_edit deliberately left blank

    vm = dialog.get_vm()

    assert vm.vlan_uid == vlan.uid
    assert vm.ip_address == ""


def test_editing_a_vm_preloads_its_assigned_vlan():
    vlan = Vlan.create_default()
    vlan.name = "Mgmt"
    existing = VirtualMachine.create_default()
    existing.vlan_uid = vlan.uid

    dialog = VMDialog(existing, vlans=[vlan])

    assert "Mgmt" in dialog.vlan_combo.currentText()


def test_editing_a_vm_with_no_vlan_shows_none():
    existing = VirtualMachine.create_default()
    vlan = Vlan.create_default()

    dialog = VMDialog(existing, vlans=[vlan])

    assert dialog.vlan_combo.currentText() == "(none)"


def test_editing_a_vm_whose_vlan_was_deleted_falls_back_to_none():
    """The VM's vlan_uid points at a uid no longer in the vlans list
    (e.g. loaded from a file after the VLAN was deleted elsewhere) -
    must not crash, just show unassigned."""
    existing = VirtualMachine.create_default()
    existing.vlan_uid = "some-deleted-uid"

    dialog = VMDialog(existing, vlans=[])

    assert dialog.vlan_combo.currentText() == "(none)"
