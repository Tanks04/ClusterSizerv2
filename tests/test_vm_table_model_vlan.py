"""Real Qt tests for VMTableModel's VLAN column."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.models.vm_table_model import VMTableModel
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_vlan_column_shows_assigned_vlan_name():
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid

    model = VMTableModel([vm], vlans_provider=lambda: [vlan])
    index = model.index(0, 11)  # VLAN column

    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "DMZ"


def test_vlan_column_shows_dash_when_unassigned():
    vm = VirtualMachine.create_default()

    model = VMTableModel([vm], vlans_provider=lambda: [])
    index = model.index(0, 11)

    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "-"


def test_vlan_column_shows_dash_for_a_stale_reference():
    """The VM points at a uid that no longer matches any current VLAN
    (e.g. deleted) - must not crash."""
    vm = VirtualMachine.create_default()
    vm.vlan_uid = "deleted-uid"

    model = VMTableModel([vm], vlans_provider=lambda: [])
    index = model.index(0, 11)

    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "-"
