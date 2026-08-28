"""Real Qt tests for BackupDestinationDialog's Location field and the
new Cloud destination type."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.backup_destination_dialog import BackupDestinationDialog
from src.models.backup_destination import BackupDestination


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_cloud_is_a_selectable_type():
    dialog = BackupDestinationDialog()
    items = [dialog.type_combo.itemText(i) for i in range(dialog.type_combo.count())]
    assert "Cloud" in items


def test_get_destination_reflects_location_and_cloud_type():
    dialog = BackupDestinationDialog()
    dialog.type_combo.setCurrentText("Cloud")
    dialog.location_edit.setText("Azure Blob Storage - West Europe")

    destination = dialog.get_destination()

    assert destination.destination_type == "Cloud"
    assert destination.location == "Azure Blob Storage - West Europe"


def test_editing_an_existing_destination_preloads_location():
    existing = BackupDestination.create_default()
    existing.location = "Iron Mountain Vault Zagreb"

    dialog = BackupDestinationDialog(existing)

    assert dialog.location_edit.text() == "Iron Mountain Vault Zagreb"
