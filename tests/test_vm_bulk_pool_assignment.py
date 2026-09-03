"""Tests for the "Add Pool" toolbar row on the VMs tab - bulk-assigns a
VM to a specific StoragePool (and its parent array too, since a pool
implies which array it belongs to), the pool-level counterpart to the
existing "Add Storage Array" row. Reported directly as the next needed
piece after building the StoragePool model/dialogs themselves.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.models.storage import Storage, StoragePool
from src.models.virtual_machine import VirtualMachine
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _storage_with_pools():
    storage = Storage.create_default()
    storage.name = "TieredArray"
    storage.pools = [
        StoragePool(uid="p1", name="DB-DWH"),
        StoragePool(uid="p2", name="OS-Pool"),
    ]
    return storage


def _vms(service, count=3):
    vms = []
    for i in range(count):
        vm = VirtualMachine.create_default()
        vm.name = f"vm-{i}"
        service.add_vm(vm)
        vms.append(vm)
    return vms


def test_pool_combo_lists_pools_with_their_array_name():
    service = ProjectService()
    service.add_storage(_storage_with_pools())
    page = VirtualMachinesPage(service)

    items = [page.bulk_pool_combo.itemText(i) for i in range(page.bulk_pool_combo.count())]

    assert "DB-DWH (TieredArray)" in items
    assert "OS-Pool (TieredArray)" in items


def test_pool_combo_empty_when_no_pools_defined():
    service = ProjectService()
    service.add_storage(Storage.create_default())  # no pools
    page = VirtualMachinesPage(service)

    assert page.bulk_pool_combo.count() == 0


def test_move_selected_to_pool_sets_both_storage_and_pool():
    service = ProjectService()
    storage = _storage_with_pools()
    service.add_storage(storage)
    vms = _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectRow(0)

    page._set_pool_for_selected_from_combo()

    assert vms[0].storage_uid == storage.uid
    assert vms[0].storage_pool_uid == "p1"
    assert vms[1].storage_pool_uid == ""
    assert vms[2].storage_pool_uid == ""


def test_move_selected_to_pool_with_no_selection_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    service.add_storage(_storage_with_pools())
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    page._set_pool_for_selected_from_combo()

    assert informed.get("called") is True


def test_move_all_to_pool_assigns_every_vm():
    service = ProjectService()
    storage = _storage_with_pools()
    service.add_storage(storage)
    _vms(service, 5)
    page = VirtualMachinesPage(service)
    page.bulk_pool_combo.setCurrentIndex(1)  # OS-Pool

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_all_vms_pool()

    assert all(vm.storage_pool_uid == "p2" for vm in service.project.vms)
    assert all(vm.storage_uid == storage.uid for vm in service.project.vms)


def test_move_all_to_pool_cancelled_changes_nothing():
    service = ProjectService()
    service.add_storage(_storage_with_pools())
    _vms(service, 5)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        page._set_all_vms_pool()

    assert all(vm.storage_pool_uid == "" for vm in service.project.vms)


def test_no_pools_yet_shows_a_helpful_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    service.add_storage(Storage.create_default())  # no pools
    _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._set_pool_for_selected_from_combo()

    assert informed.get("called") is True


def test_pool_bulk_assignment_is_one_undo_step():
    service = ProjectService()
    storage = _storage_with_pools()
    service.add_storage(storage)
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_all_vms_pool()
    assert all(vm.storage_pool_uid == "p1" for vm in service.project.vms)

    service.undo()

    assert all(vm.storage_pool_uid == "" for vm in service.project.vms)


def test_pool_widgets_hidden_by_default():
    service = ProjectService()
    service.add_storage(_storage_with_pools())
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    assert page.pool_move_widgets.isVisible() is False


def test_pool_widgets_shown_when_advanced_enabled():
    service = ProjectService()
    service.add_storage(_storage_with_pools())
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    page.set_advanced_mode(True)
    QApplication.processEvents()

    assert page.pool_move_widgets.isVisible() is True


def test_storage_array_label_renamed_for_consistency():
    """The array-level row was originally labeled "Add Storage Pool"
    before pools existed as their own concept - renamed to "Add
    Storage Array" to avoid colliding with the new pool-specific row."""
    service = ProjectService()
    page = VirtualMachinesPage(service)

    from PySide6.QtWidgets import QLabel
    label_texts = [w.text() for w in page.storage_move_widgets.findChildren(QLabel)]
    assert "Add Storage Array:" in label_texts
