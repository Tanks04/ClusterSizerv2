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


def test_storage_calculator_row_hidden_when_hci_checked():
    dialog = StorageDialog(servers=[])

    dialog.is_hci_check.setChecked(True)

    assert dialog.form_layout.isRowVisible(dialog.disk_calc_button.parentWidget()) is False


def test_storage_calculator_row_shown_when_hci_unchecked_again():
    dialog = StorageDialog(servers=[])
    dialog.is_hci_check.setChecked(True)

    dialog.is_hci_check.setChecked(False)

    assert dialog.form_layout.isRowVisible(dialog.disk_calc_button.parentWidget()) is True


def test_storage_fields_persist_through_load():
    from src.models.storage import Storage

    existing = Storage.create_default()
    existing.disk_count = 24
    existing.disk_size_tb = 2.0

    dialog = StorageDialog(existing, servers=[])

    assert dialog.disk_count_spin.value() == 24
    assert dialog.disk_size_spin.value() == 2.0


# ----------------------------------------------------------------------
# RAID-level Usable estimate - the ZFS/non-uniform-disk scenario
# discussed directly: pick a RAID level, Calc also fills Usable with a
# rough estimate, but it stays independently editable afterward so a
# real (non-uniform-disk) number can always override it.
# ----------------------------------------------------------------------

def test_raid5_calc_fills_both_raw_and_usable():
    dialog = StorageDialog(servers=[])
    dialog.disk_count_spin.setValue(12)
    dialog.disk_size_spin.setValue(1.0)
    dialog.raid_level_combo.setCurrentText("RAID 5")

    dialog._calculate_raw_capacity()

    assert dialog.raw_spin.value() == 12.0
    assert dialog.usable_spin.value() == 11.0  # RAID5 = N-1 disks


def test_raid6_usable_estimate():
    dialog = StorageDialog(servers=[])
    dialog.disk_count_spin.setValue(12)
    dialog.disk_size_spin.setValue(2.0)
    dialog.raid_level_combo.setCurrentText("RAID 6")

    dialog._calculate_raw_capacity()

    assert dialog.usable_spin.value() == 20.0  # (12-2) * 2 TB


def test_raid10_usable_estimate():
    dialog = StorageDialog(servers=[])
    dialog.disk_count_spin.setValue(12)
    dialog.disk_size_spin.setValue(1.0)
    dialog.raid_level_combo.setCurrentText("RAID 1 / RAID 10")

    dialog._calculate_raw_capacity()

    assert dialog.usable_spin.value() == 6.0  # 12/2 disks


def test_no_raid_selected_leaves_usable_untouched():
    dialog = StorageDialog(servers=[])
    dialog.usable_spin.setValue(42.0)
    dialog.disk_count_spin.setValue(10)
    dialog.disk_size_spin.setValue(2.0)
    # raid_level_combo left at default "(none - Raw only)"

    dialog._calculate_raw_capacity()

    assert dialog.raw_spin.value() == 20.0
    assert dialog.usable_spin.value() == 42.0  # untouched


def test_usable_stays_editable_after_raid_estimate():
    dialog = StorageDialog(servers=[])
    dialog.disk_count_spin.setValue(12)
    dialog.disk_size_spin.setValue(1.0)
    dialog.raid_level_combo.setCurrentText("RAID 5")
    dialog._calculate_raw_capacity()

    dialog.usable_spin.setValue(9.5)  # manual override for non-uniform disks

    storage = dialog.get_storage()
    assert storage.usable_capacity_tb == 9.5


def test_raid_level_persists_through_load():
    from src.models.storage import Storage

    existing = Storage.create_default()
    existing.raid_level = "RAID 6"

    dialog = StorageDialog(existing, servers=[])

    assert dialog.raid_level_combo.currentData() == "RAID 6"


def test_stale_raid_level_falls_back_to_none():
    from src.models.storage import Storage

    existing = Storage.create_default()
    existing.raid_level = "Some Deleted Custom Level"

    dialog = StorageDialog(existing, servers=[])

    assert dialog.raid_level_combo.currentIndex() == 0


# ----------------------------------------------------------------------
# FTT-based HCI Usable estimate - reversed gating from the RAID/disk-
# count calculator: shown ONLY when HCI is checked, since Raw comes
# from linked servers rather than a manual disk count in that mode.
# ----------------------------------------------------------------------

def test_ftt_row_hidden_by_default_non_hci():
    dialog = StorageDialog(servers=[])

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is False


def test_ftt_row_shown_when_hci_checked():
    dialog = StorageDialog(servers=[])

    dialog.is_hci_check.setChecked(True)

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is True
    assert dialog.form_layout.isRowVisible(dialog.disk_calc_button.parentWidget()) is False


def test_ftt_row_hidden_again_when_hci_unchecked():
    dialog = StorageDialog(servers=[])
    dialog.is_hci_check.setChecked(True)

    dialog.is_hci_check.setChecked(False)

    assert dialog.form_layout.isRowVisible(dialog.ftt_container) is False
    assert dialog.form_layout.isRowVisible(dialog.disk_calc_button.parentWidget()) is True


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
