"""Tests for a critical bug fix and follow-up UI improvements to
Storage Pools: opening the RAID Calculator from a BRAND NEW (not yet
saved) pool had no valid project entity to target, so its "Which one"
list only offered EXISTING pools - applying would silently overwrite
one of those instead of creating the new pool. Also covers the
simplified section title, a visible "Disks" summary in
StoragePoolDialog (mirroring StorageDialog's own), and an aggregate
disk-count display so it's easy to see totals across pools.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.models.storage import Storage, StoragePool
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# The critical bug: new pool + RAID Calculator overwrote an existing one
# ----------------------------------------------------------------------

def test_new_pool_calculator_locks_to_none_mode():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Existing")]
    service.add_storage(storage)

    dialog = RaidCalculatorDialog(service, locked_target=("None", None))

    assert dialog.target_type_combo.currentText() == "None (just calculating)"
    assert "New pool" in dialog.locked_target_label.text()


def test_new_pool_calculator_hides_the_picker():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    dialog = RaidCalculatorDialog(service, locked_target=("None", None))
    dialog.show()
    QApplication.processEvents()

    target_form = dialog.target_type_combo.parentWidget().layout()
    assert target_form.isRowVisible(dialog.target_type_combo) is False
    assert dialog.locked_target_label.isVisible() is True


def test_new_pool_gets_its_own_values_not_an_existing_pools():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    existing = StoragePool(uid="p1", name="Existing", disk_count=5, disk_size_tb=4.0,
                            raw_capacity_tb=20.0, usable_capacity_tb=16.0)
    storage.pools = [existing]
    service.add_storage(storage)
    new_pool_dialog = StoragePoolDialog(servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(10)
        self.disk_size_spin.setValue(12.0)
        self.raid_level_combo.setCurrentText("RAID 6")
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        new_pool_dialog._open_raid_calculator()

    result = new_pool_dialog.get_pool()
    assert result.disk_count == 10
    assert result.raw_capacity_tb == 120.0


def test_existing_pool_is_never_touched_by_a_new_pools_calculation():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    existing = StoragePool(uid="p1", name="Existing", disk_count=5, disk_size_tb=4.0,
                            raw_capacity_tb=20.0, usable_capacity_tb=16.0)
    storage.pools = [existing]
    service.add_storage(storage)
    new_pool_dialog = StoragePoolDialog(servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(10)
        self.disk_size_spin.setValue(12.0)
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        new_pool_dialog._open_raid_calculator()

    untouched = service.project.storages[0].pools[0]
    assert untouched.disk_count == 5
    assert untouched.raw_capacity_tb == 20.0


def test_existing_pool_still_uses_the_locked_target_flow():
    """Regression guard - fixing the new-pool case must not break the
    already-working existing-pool expand workflow."""
    from PySide6.QtWidgets import QMessageBox

    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="Pool1", disk_count=7, disk_size_tb=15.0, raw_capacity_tb=105.0)
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = StoragePoolDialog(pool, service=service)

    def fake_exec(self):
        assert self.target_type_combo.currentText() == "Storage Pool"
        self.disk_count_spin.setValue(11)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self._apply_to_pool((0, 0))
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        dialog._open_raid_calculator()

    assert service.project.storages[0].pools[0].disk_count == 11


# ----------------------------------------------------------------------
# Section title simplification
# ----------------------------------------------------------------------

def test_pools_section_title_simplified():
    from src.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog(servers=[])

    pools_box = next(
        w for w in dialog.findChildren(type(dialog.pools_table.parentWidget()))
        if hasattr(w, "title") and w.title() == "Storage Pools"
    )
    assert pools_box.title() == "Storage Pools"


# ----------------------------------------------------------------------
# StoragePoolDialog - visible disk summary (mirroring StorageDialog's)
# ----------------------------------------------------------------------

def test_new_pool_shows_not_yet_configured():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()

    assert "Not yet configured" in dialog.disk_summary_label.text()


def test_existing_pool_shows_its_disk_composition():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    pool = StoragePool(uid="p1", name="Pool", disk_count=10, disk_size_tb=12.0, raid_level="RAID 5")

    dialog = StoragePoolDialog(pool)

    assert dialog.disk_summary_label.text() == "10x 12TB, RAID 5"


def test_pool_disk_summary_refreshes_after_calculator_for_new_pool():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    dialog = StoragePoolDialog(servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(8)
        self.disk_size_spin.setValue(4.0)
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        dialog._open_raid_calculator()

    assert "8x 4TB" in dialog.disk_summary_label.text()


# ----------------------------------------------------------------------
# Pools table Disks column + aggregate total
# ----------------------------------------------------------------------

def test_pools_table_shows_disk_composition_per_pool():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.pools = [
        StoragePool(uid="p1", name="NVMe-Pool", disk_count=7, disk_size_tb=15.0),
        StoragePool(uid="p2", name="SAS-Pool", disk_count=10, disk_size_tb=2.0),
    ]

    dialog = StorageDialog(storage, servers=[])

    assert dialog.pools_table.item(0, 1).text() == "7x 15TB"
    assert dialog.pools_table.item(1, 1).text() == "10x 2TB"


def test_pools_table_shows_dash_for_pool_with_no_disk_data():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Pool")]

    dialog = StorageDialog(storage, servers=[])

    assert dialog.pools_table.item(0, 1).text() == "-"


def test_total_disks_label_sums_across_pools():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.pools = [
        StoragePool(uid="p1", name="A", disk_count=7),
        StoragePool(uid="p2", name="B", disk_count=10),
    ]

    dialog = StorageDialog(storage, servers=[])

    assert dialog.total_disks_label.text() == "Total across pools: 17 disks"


def test_total_disks_label_falls_back_to_whole_array_when_no_pools():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.disk_count = 24

    dialog = StorageDialog(storage, servers=[])

    assert dialog.total_disks_label.text() == "Total (whole array, no pools): 24 disks"


def test_total_disks_label_empty_when_nothing_configured():
    from src.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog(servers=[])

    assert dialog.total_disks_label.text() == ""


def test_total_disks_label_updates_after_adding_a_pool():
    from src.gui.dialogs.storage_dialog import StorageDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StorageDialog(servers=[])
    new_pool = StoragePool(uid="p1", name="Pool", disk_count=12)

    with patch.object(StoragePoolDialog, "exec", return_value=True), \
         patch.object(StoragePoolDialog, "get_pool", return_value=new_pool):
        dialog._add_pool()

    assert dialog.total_disks_label.text() == "Total across pools: 12 disks"
