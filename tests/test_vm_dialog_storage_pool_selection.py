"""Tests for VMDialog's storage_pool_combo - lets a VM be assigned to a
specific pool WITHIN the selected storage array, not just the array as
a whole. Populated dynamically from the currently-selected array's own
pools, and only shown when that array actually has pools defined.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.vm_dialog import VMDialog
from src.models.storage import Storage, StoragePool
from src.models.virtual_machine import VirtualMachine
from src.persistence import app_preferences


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "preferences.json")
    app_preferences.set_advanced_mode(True)  # storage assignment is advanced-only
    yield


def _storage_with_pools(name="TieredArray", pool_names=("SSD-Tier", "SATA-Tier")):
    storage = Storage.create_default()
    storage.name = name
    storage.pools = [StoragePool(uid=f"p{i}", name=n) for i, n in enumerate(pool_names)]
    return storage


def test_pool_row_hidden_when_no_storage_selected():
    dialog = VMDialog(storages=[_storage_with_pools()])

    assert dialog.form_layout.isRowVisible(dialog.storage_pool_combo) is False


def test_pool_row_hidden_for_array_without_pools():
    plain = Storage.create_default()
    plain.name = "SimpleArray"
    dialog = VMDialog(storages=[plain])

    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(plain.uid))

    assert dialog.form_layout.isRowVisible(dialog.storage_pool_combo) is False


def test_pool_row_shown_for_array_with_pools():
    tiered = _storage_with_pools()
    dialog = VMDialog(storages=[tiered])

    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))

    assert dialog.form_layout.isRowVisible(dialog.storage_pool_combo) is True


def test_pool_combo_lists_the_selected_arrays_own_pools():
    tiered = _storage_with_pools()
    dialog = VMDialog(storages=[tiered])

    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))

    items = [dialog.storage_pool_combo.itemText(i) for i in range(dialog.storage_pool_combo.count())]
    assert "SSD-Tier" in items
    assert "SATA-Tier" in items


def test_switching_arrays_updates_the_pool_list():
    tiered = _storage_with_pools("Tiered", ("Fast", "Slow"))
    other = _storage_with_pools("Other", ("Bronze",))
    dialog = VMDialog(storages=[tiered, other])

    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))
    first_items = {dialog.storage_pool_combo.itemText(i) for i in range(dialog.storage_pool_combo.count())}

    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(other.uid))
    second_items = {dialog.storage_pool_combo.itemText(i) for i in range(dialog.storage_pool_combo.count())}

    assert "Fast" in first_items and "Bronze" not in first_items
    assert "Bronze" in second_items and "Fast" not in second_items


def test_selecting_a_pool_and_saving():
    tiered = _storage_with_pools()
    dialog = VMDialog(storages=[tiered])
    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))
    dialog.storage_pool_combo.setCurrentIndex(dialog.storage_pool_combo.findData("p0"))

    vm = dialog.get_vm()

    assert vm.storage_uid == tiered.uid
    assert vm.storage_pool_uid == "p0"


def test_none_selected_saves_empty_pool_uid():
    tiered = _storage_with_pools()
    dialog = VMDialog(storages=[tiered])
    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))
    # storage_pool_combo left at default "(none)"

    vm = dialog.get_vm()

    assert vm.storage_pool_uid == ""


def test_editing_existing_vm_preloads_its_pool():
    tiered = _storage_with_pools()
    vm = VirtualMachine.create_default()
    vm.storage_uid = tiered.uid
    vm.storage_pool_uid = "p1"

    dialog = VMDialog(vm, storages=[tiered])

    assert dialog.form_layout.isRowVisible(dialog.storage_pool_combo) is True
    assert dialog.storage_pool_combo.currentData() == "p1"


def test_editing_existing_vm_with_stale_pool_reference_falls_back_to_none():
    tiered = _storage_with_pools()
    vm = VirtualMachine.create_default()
    vm.storage_uid = tiered.uid
    vm.storage_pool_uid = "deleted-pool-uid"

    dialog = VMDialog(vm, storages=[tiered])

    assert dialog.storage_pool_combo.currentIndex() == 0


def test_pool_row_hidden_when_advanced_mode_off(monkeypatch, tmp_path):
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "off.json")
    app_preferences.set_advanced_mode(False)
    tiered = _storage_with_pools()

    dialog = VMDialog(storages=[tiered])
    dialog.storage_combo.setCurrentIndex(dialog.storage_combo.findData(tiered.uid))

    assert dialog.form_layout.isRowVisible(dialog.storage_pool_combo) is False
