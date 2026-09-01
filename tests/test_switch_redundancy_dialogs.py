"""Real Qt tests for the GUI side of switch redundancy - SwitchDialog's
Redundancy Group/Role fields and ConnectionDialog's new Switch<->Switch
connection type plus the Dedicated Link checkbox."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.switch_dialog import SwitchDialog
from src.gui.dialogs.connection_dialog import ConnectionDialog
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection, KIND_SWITCH_SWITCH
from src.models.cluster_project import ClusterProject


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# SwitchDialog
# ----------------------------------------------------------------------

def test_new_switch_defaults_to_no_redundancy():
    dialog = SwitchDialog()

    switch = dialog.get_switch()

    assert switch.redundancy_group == ""
    assert switch.redundancy_role == ""


def test_setting_redundancy_group_and_role():
    dialog = SwitchDialog()
    dialog.redundancy_group_edit.setText("fw-pair-01")
    dialog.redundancy_role_combo.setCurrentText("Active")

    switch = dialog.get_switch()

    assert switch.redundancy_group == "fw-pair-01"
    assert switch.redundancy_role == "Active"


def test_editing_preloads_redundancy_fields():
    existing = NetworkSwitch.create_default()
    existing.redundancy_group = "core-pair-01"
    existing.redundancy_role = "Standby"

    dialog = SwitchDialog(existing)

    assert dialog.redundancy_group_edit.text() == "core-pair-01"
    assert dialog.redundancy_role_combo.currentData() == "Standby"


def test_role_dropdown_offers_common_vendor_terms():
    dialog = SwitchDialog()

    items = [dialog.redundancy_role_combo.itemText(i) for i in range(dialog.redundancy_role_combo.count())]

    assert items == ["(none)", "Active", "Standby", "Passive", "Member"]


# ----------------------------------------------------------------------
# ConnectionDialog - Switch<->Switch + Dedicated Link
# ----------------------------------------------------------------------

def test_switch_switch_kind_available():
    project = ClusterProject()
    dialog = ConnectionDialog(project)

    kinds = [dialog.type_combo.itemData(i) for i in range(dialog.type_combo.count())]

    assert KIND_SWITCH_SWITCH in kinds


def test_creating_a_switch_to_switch_connection():
    project = ClusterProject()
    sw1 = NetworkSwitch.create_default()
    sw1.name = "fw-01"
    sw2 = NetworkSwitch.create_default()
    sw2.name = "fw-02"
    project.switches.extend([sw1, sw2])
    dialog = ConnectionDialog(project)
    idx = dialog.type_combo.findData(KIND_SWITCH_SWITCH)
    dialog.type_combo.setCurrentIndex(idx)
    dialog.combo_a.setCurrentIndex(0)
    dialog.combo_b.setCurrentIndex(1)
    dialog.dedicated_link_check.setChecked(True)

    connection = dialog.get_connection()

    assert connection.switch_uid == sw1.uid
    assert connection.switch_b_uid == sw2.uid
    assert connection.dedicated_link is True
    assert connection.server_uid == ""
    assert connection.storage_uid == ""


def test_editing_an_existing_switch_to_switch_connection():
    project = ClusterProject()
    sw1 = NetworkSwitch.create_default()
    sw1.name = "fw-01"
    sw2 = NetworkSwitch.create_default()
    sw2.name = "fw-02"
    project.switches.extend([sw1, sw2])
    existing = NetworkConnection.create_default()
    existing.switch_uid = sw1.uid
    existing.switch_b_uid = sw2.uid
    existing.dedicated_link = True
    project.connections.append(existing)

    dialog = ConnectionDialog(project, existing)

    assert dialog.combo_a.currentData() == sw1.uid
    assert dialog.combo_b.currentData() == sw2.uid
    assert dialog.dedicated_link_check.isChecked() is True


def test_dedicated_link_defaults_unchecked_for_a_new_connection():
    project = ClusterProject()
    dialog = ConnectionDialog(project)

    assert dialog.dedicated_link_check.isChecked() is False


def test_switching_away_from_switch_switch_clears_switch_b_uid():
    """Reported-pattern regression check: switching a connection's type
    away from Switch<->Switch must not leave a stale switch_b_uid."""
    project = ClusterProject()
    server = None
    from src.models.server import Server
    server = Server.create_default()
    server.name = "srv-01"
    sw1 = NetworkSwitch.create_default()
    sw1.name = "sw-01"
    sw2 = NetworkSwitch.create_default()
    sw2.name = "sw-02"
    project.servers.append(server)
    project.switches.extend([sw1, sw2])
    existing = NetworkConnection.create_default()
    existing.switch_uid = sw1.uid
    existing.switch_b_uid = sw2.uid
    project.connections.append(existing)

    dialog = ConnectionDialog(project, existing)
    from src.models.network_connection import KIND_SERVER_SWITCH
    idx = dialog.type_combo.findData(KIND_SERVER_SWITCH)
    dialog.type_combo.setCurrentIndex(idx)
    dialog.combo_a.setCurrentIndex(0)
    dialog.combo_b.setCurrentIndex(0)

    connection = dialog.get_connection()

    assert connection.switch_b_uid == ""
