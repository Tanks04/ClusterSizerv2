"""Real Qt tests for ServerDialog's inventory fields (Serial Number,
BMC IP, Hypervisor vendor/version)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.server_dialog import ServerDialog
from src.models.server import Server


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_new_server_defaults_hypervisor_to_blank():
    dialog = ServerDialog()
    assert dialog.hypervisor_vendor_combo.currentText() == ""


def test_get_server_reflects_entered_inventory_fields():
    dialog = ServerDialog()
    dialog.serial_number_edit.setText("SN12345")
    dialog.bmc_ip_edit.setText("10.10.99.10")
    dialog.hypervisor_vendor_combo.setCurrentText("VMware (ESXi / vSphere)")
    dialog.hypervisor_version_edit.setText("8.0 U2")

    server = dialog.get_server()

    assert server.serial_number == "SN12345"
    assert server.bmc_ip == "10.10.99.10"
    assert server.hypervisor_vendor == "VMware (ESXi / vSphere)"
    assert server.hypervisor_version == "8.0 U2"


def test_editing_an_existing_server_preloads_inventory_fields():
    existing = Server.create_default()
    existing.serial_number = "SN99"
    existing.hypervisor_vendor = "Nutanix AHV"

    dialog = ServerDialog(existing)

    assert dialog.serial_number_edit.text() == "SN99"
    assert dialog.hypervisor_vendor_combo.currentText() == "Nutanix AHV"


def test_unknown_hypervisor_value_falls_back_to_blank_without_crashing():
    """A value that predates a change to HYPERVISOR_VENDORS, or was
    never a valid option, must not crash the dialog."""
    existing = Server.create_default()
    existing.hypervisor_vendor = "SomeDiscontinuedHypervisor"

    dialog = ServerDialog(existing)

    assert dialog.hypervisor_vendor_combo.currentIndex() == 0
