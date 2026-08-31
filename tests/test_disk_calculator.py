"""Real Qt tests for the disk count x size calculators on ServerDialog
(local disk) and StorageDialog (array capacity) - fills the actual Raw
field as a convenience, but that field stays independently editable
afterward, and the Storage calculator is disabled while HCI is checked
since that field is auto-summed from linked servers instead."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.dialogs.storage_dialog import StorageDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_server_calculator_fills_local_disk_raw():
    dialog = ServerDialog()
    dialog.local_disk_count_spin.setValue(12)
    dialog.local_disk_size_spin.setValue(1.09)

    dialog._calculate_local_disk_raw()

    assert abs(dialog.local_disk_spin.value() - 13.08) < 0.01


def test_server_calculator_does_nothing_with_zero_count_or_size():
    dialog = ServerDialog()
    dialog.local_disk_spin.setValue(5.0)
    dialog.local_disk_count_spin.setValue(0)
    dialog.local_disk_size_spin.setValue(2.0)

    dialog._calculate_local_disk_raw()

    assert dialog.local_disk_spin.value() == 5.0  # untouched


def test_server_raw_stays_editable_after_calculation():
    dialog = ServerDialog()
    dialog.local_disk_count_spin.setValue(12)
    dialog.local_disk_size_spin.setValue(1.09)
    dialog._calculate_local_disk_raw()

    dialog.local_disk_spin.setValue(20.0)  # manual override afterward

    server = dialog.get_server()
    assert server.local_disk_raw_tb == 20.0


def test_storage_calculator_fills_raw_capacity():
    dialog = StorageDialog(servers=[])
    dialog.disk_count_spin.setValue(24)
    dialog.disk_size_spin.setValue(2.0)

    dialog._calculate_raw_capacity()

    assert dialog.raw_spin.value() == 48.0


def test_storage_calculator_button_disabled_when_hci_checked():
    dialog = StorageDialog(servers=[])

    dialog.is_hci_check.setChecked(True)

    assert dialog.disk_calc_button.isEnabled() is False


def test_storage_calculator_button_re_enabled_when_hci_unchecked():
    dialog = StorageDialog(servers=[])
    dialog.is_hci_check.setChecked(True)

    dialog.is_hci_check.setChecked(False)

    assert dialog.disk_calc_button.isEnabled() is True


def test_storage_fields_persist_through_load():
    from src.models.storage import Storage

    existing = Storage.create_default()
    existing.disk_count = 24
    existing.disk_size_tb = 2.0

    dialog = StorageDialog(existing, servers=[])

    assert dialog.disk_count_spin.value() == 24
    assert dialog.disk_size_spin.value() == 2.0
