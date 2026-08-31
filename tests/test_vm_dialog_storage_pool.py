"""Real Qt tests for VMDialog's Storage Pool dropdown - assigns a VM to
a SPECIFIC Storage entity, independent of the site-wide aggregate,
matching the exact pattern already established for VLAN assignment."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.vm_dialog import VMDialog
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_no_storages_available_shows_only_none_option():
    dialog = VMDialog()
    assert dialog.storage_combo.count() == 1
    assert "(none" in dialog.storage_combo.currentText()


def test_new_vm_defaults_to_no_storage_pool():
    storage = Storage.create_default()
    storage.name = "Pool A"
    dialog = VMDialog(storages=[storage])

    vm = dialog.get_vm()

    assert vm.storage_uid == ""


def test_selecting_a_pool_sets_storage_uid():
    storage = Storage.create_default()
    storage.name = "Pool A"
    dialog = VMDialog(storages=[storage])

    dialog.storage_combo.setCurrentIndex(1)
    vm = dialog.get_vm()

    assert vm.storage_uid == storage.uid


def test_editing_a_vm_preloads_its_assigned_pool():
    storage = Storage.create_default()
    storage.name = "Pool B"
    existing = VirtualMachine.create_default()
    existing.storage_uid = storage.uid

    dialog = VMDialog(existing, storages=[storage])

    assert "Pool B" in dialog.storage_combo.currentText()


def test_editing_a_vm_with_no_pool_shows_none():
    storage = Storage.create_default()
    existing = VirtualMachine.create_default()

    dialog = VMDialog(existing, storages=[storage])

    assert dialog.storage_combo.currentIndex() == 0


def test_editing_a_vm_whose_pool_was_deleted_falls_back_to_none():
    existing = VirtualMachine.create_default()
    existing.storage_uid = "some-deleted-uid"

    dialog = VMDialog(existing, storages=[])

    assert dialog.storage_combo.currentIndex() == 0
