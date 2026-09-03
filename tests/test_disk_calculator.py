"""Real Qt tests for the disk-size calculator on ServerDialog (local
disk) and the FTT calculator on StorageDialog (HCI Usable estimate).
The old inline disk-count/RAID-level calculator that used to live on
StorageDialog was removed entirely - replaced by a button that opens
the much more capable standalone RAID Calculator tool (its own tests
live in test_raid_calculator.py) - see test_storage_dialog_raid_
calculator_button.py for that integration.
"""

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


# ----------------------------------------------------------------------
# FTT-based HCI Usable estimate - reversed gating from the RAID
# Calculator button: shown ONLY when HCI is checked, since Raw comes
# from linked servers rather than a manual disk count in that mode.
# ----------------------------------------------------------------------

def test_ftt_row_hidden_by_default_non_hci():
    dialog = StorageDialog(servers=[])

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is False


def test_ftt_row_shown_when_hci_checked():
    dialog = StorageDialog(servers=[])

    dialog.is_hci_check.setChecked(True)

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is True
    assert dialog.form_layout.isRowVisible(dialog.raid_calc_button) is False


def test_ftt_row_hidden_again_when_hci_unchecked():
    dialog = StorageDialog(servers=[])
    dialog.is_hci_check.setChecked(True)

    dialog.is_hci_check.setChecked(False)

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is False
    assert dialog.form_layout.isRowVisible(dialog.raid_calc_button) is True


def test_ftt1_mirroring_usable_estimate():
    dialog = StorageDialog(servers=[])
    dialog.raw_spin.setValue(96.0)
    dialog.ftt_level_combo.setCurrentText("FTT=1 Mirroring")

    dialog._calculate_hci_usable()

    assert dialog.usable_spin.value() == 48.0


def test_ftt1_erasure_coding_usable_estimate():
    dialog = StorageDialog(servers=[])
    dialog.raw_spin.setValue(100.0)
    dialog.ftt_level_combo.setCurrentText("FTT=1 Erasure Coding")

    dialog._calculate_hci_usable()

    assert dialog.usable_spin.value() == 75.0


def test_no_ftt_selected_leaves_usable_untouched():
    dialog = StorageDialog(servers=[])
    dialog.usable_spin.setValue(42.0)
    dialog.raw_spin.setValue(96.0)
    # ftt_level_combo left at default "(none)"

    dialog._calculate_hci_usable()

    assert dialog.usable_spin.value() == 42.0


def test_usable_stays_editable_after_ftt_estimate():
    dialog = StorageDialog(servers=[])
    dialog.raw_spin.setValue(96.0)
    dialog.ftt_level_combo.setCurrentText("FTT=1 Mirroring")
    dialog._calculate_hci_usable()

    dialog.usable_spin.setValue(45.0)

    storage = dialog.get_storage()
    assert storage.usable_capacity_tb == 45.0


def test_ftt_level_persists_through_load():
    from src.models.storage import Storage

    existing = Storage.create_default()
    existing.ftt_level = "FTT=2 Mirroring"

    dialog = StorageDialog(existing, servers=[])

    assert dialog.ftt_level_combo.currentData() == "FTT=2 Mirroring"
