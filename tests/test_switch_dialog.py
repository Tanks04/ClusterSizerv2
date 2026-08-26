"""Real Qt tests for SwitchDialog, covering the Firewall/Load Balancer
type addition - the Network tab's device types were previously limited
to LAN/SAN-FC/Unified, with no way to represent a firewall or load
balancer despite the entity's existing fields (rack/power/price/ports)
being generic enough to already fit any rack-mounted network appliance.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.switch_dialog import SwitchDialog
from src.models.network_switch import SWITCH_TYPES, NetworkSwitch


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_type_dropdown_includes_firewall_and_load_balancer():
    dialog = SwitchDialog()
    items = [dialog.type_combo.itemText(i) for i in range(dialog.type_combo.count())]

    assert "Firewall" in items
    assert "Load Balancer" in items
    assert items == SWITCH_TYPES  # dialog uses the shared constant, not its own hardcoded copy


def test_dialog_title_reflects_any_network_device_not_just_switches():
    dialog = SwitchDialog()
    assert dialog.windowTitle() == "Network Device"


def test_saving_a_firewall_round_trips_correctly():
    dialog = SwitchDialog()
    dialog.name_edit.setText("fw-01")
    dialog.type_combo.setCurrentText("Firewall")

    device = dialog.get_switch()

    assert device.name == "fw-01"
    assert device.switch_type == "Firewall"


def test_editing_an_existing_load_balancer_preloads_its_type():
    existing = NetworkSwitch.create_default()
    existing.name = "lb-01"
    existing.switch_type = "Load Balancer"

    dialog = SwitchDialog(existing)

    assert dialog.type_combo.currentText() == "Load Balancer"
