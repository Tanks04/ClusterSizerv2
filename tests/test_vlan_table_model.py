"""Real Qt tests for VlanTableModel, particularly the live VM-count
column."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.models.vlan_table_model import VlanTableModel
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _data(model, row, col):
    return model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole)


def test_basic_fields():
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    vlan.site = "DR"
    vlan.network = "192.168.10.0/24"
    vlan.gateway = "192.168.10.1"
    vlan.notes = "Perimeter"

    model = VlanTableModel([vlan])

    assert _data(model, 0, 0) == "DMZ"
    assert _data(model, 0, 1) == "DR"
    assert _data(model, 0, 2) == "192.168.10.0/24"
    assert _data(model, 0, 3) == "192.168.10.1"
    assert _data(model, 0, 5) == "Perimeter"


def test_empty_fields_show_dash():
    vlan = Vlan.create_default()
    model = VlanTableModel([vlan])

    assert _data(model, 0, 0) == "-"
    assert _data(model, 0, 2) == "-"
    assert _data(model, 0, 3) == "-"
    assert _data(model, 0, 5) == "-"


def test_vm_count_reflects_only_matching_vlan_uid():
    vlan1 = Vlan.create_default()
    vlan2 = Vlan.create_default()
    vm1 = VirtualMachine.create_default()
    vm1.vlan_uid = vlan1.uid
    vm2 = VirtualMachine.create_default()
    vm2.vlan_uid = vlan1.uid
    vm3 = VirtualMachine.create_default()
    vm3.vlan_uid = vlan2.uid
    vm4 = VirtualMachine.create_default()  # unassigned

    model = VlanTableModel([vlan1, vlan2], vms_provider=lambda: [vm1, vm2, vm3, vm4])

    assert _data(model, 0, 4) == "2"
    assert _data(model, 1, 4) == "1"


def test_vm_count_is_zero_with_no_vms_provider():
    vlan = Vlan.create_default()
    model = VlanTableModel([vlan])

    assert _data(model, 0, 4) == "0"


def test_set_vlans_resets_the_model():
    model = VlanTableModel()
    assert model.rowCount() == 0

    vlan = Vlan.create_default()
    model.set_vlans([vlan])

    assert model.rowCount() == 1
    assert model.vlan_at(0) is vlan
