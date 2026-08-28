"""Real Qt tests for VlanDialog."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.vlan_dialog import VlanDialog
from src.models.vlan import Vlan


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_new_vlan_defaults_to_primary_site():
    dialog = VlanDialog()
    assert dialog.site_combo.currentText() == "Primary"


def test_get_vlan_reflects_entered_fields():
    dialog = VlanDialog()
    dialog.name_edit.setText("DMZ")
    dialog.site_combo.setCurrentText("DR")
    dialog.network_edit.setText("192.168.10.0/24")
    dialog.gateway_edit.setText("192.168.10.1")
    dialog.notes_edit.setPlainText("Perimeter segment")

    vlan = dialog.get_vlan()

    assert vlan.name == "DMZ"
    assert vlan.site == "DR"
    assert vlan.network == "192.168.10.0/24"
    assert vlan.gateway == "192.168.10.1"
    assert vlan.notes == "Perimeter segment"


def test_editing_an_existing_vlan_preloads_its_fields():
    existing = Vlan.create_default()
    existing.name = "Mgmt"
    existing.site = "DR"
    existing.network = "10.0.0.0/24"

    dialog = VlanDialog(existing)

    assert dialog.name_edit.text() == "Mgmt"
    assert dialog.site_combo.currentText() == "DR"
    assert dialog.network_edit.text() == "10.0.0.0/24"


def test_editing_preserves_the_original_uid():
    existing = Vlan.create_default()
    dialog = VlanDialog(existing)
    dialog.name_edit.setText("Renamed")

    result = dialog.get_vlan()

    assert result.uid == existing.uid
