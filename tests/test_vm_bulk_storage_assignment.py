"""Real Qt tests for bulk-assigning VMs to a Storage Pool - the "Add
Storage Pool" toolbar row (Move Selected/Move All), matching the exact
pattern already established for Site/Cluster bulk assignment. Also
covers the new "Storage Pool" column on the VMs table.
"""

import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.project_service import ProjectService
from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _vms(service, count=5):
    vms = []
    for i in range(count):
        vm = VirtualMachine.create_default()
        vm.name = f"vm-{i}"
        service.add_vm(vm)
        vms.append(vm)
    return vms


# ----------------------------------------------------------------------
# Bulk move (Storage Pool) toolbar row
# ----------------------------------------------------------------------

def test_bulk_storage_combo_populated_from_project_storages():
    service = ProjectService()
    storage = Storage.create_default()
    storage.name = "SAN-Pool-1"
    service.add_storage(storage)
    page = VirtualMachinesPage(service)

    assert page.bulk_storage_combo.count() == 1
    assert page.bulk_storage_combo.currentText() == "SAN-Pool-1"
    assert page.bulk_storage_combo.currentData() == storage.uid


def test_move_selected_to_storage_only_affects_selected_vms():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    vms = _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectRow(0)

    page._set_storage_for_selected_from_combo()

    assert vms[0].storage_uid == storage.uid
    assert vms[1].storage_uid == ""
    assert vms[2].storage_uid == ""


def test_move_selected_to_storage_with_no_selection_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    page._set_storage_for_selected_from_combo()

    assert informed.get("called") is True


def test_move_all_to_storage_assigns_every_vm():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _vms(service, 5)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_all_vms_storage()

    assert all(vm.storage_uid == storage.uid for vm in service.project.vms)


def test_move_all_to_storage_cancelled_changes_nothing():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _vms(service, 5)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        page._set_all_vms_storage()

    assert all(vm.storage_uid == "" for vm in service.project.vms)


def test_no_storages_yet_shows_a_helpful_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._set_storage_for_selected_from_combo()

    assert informed.get("called") is True


def test_storage_combo_preserves_selection_across_refresh():
    service = ProjectService()
    storage_a = Storage.create_default()
    storage_a.name = "SAN-Pool-1"
    storage_b = Storage.create_default()
    storage_b.name = "SAN-Pool-2"
    service.add_storage(storage_a)
    service.add_storage(storage_b)
    page = VirtualMachinesPage(service)
    page.bulk_storage_combo.setCurrentIndex(1)

    _vms(service, 1)  # triggers a refresh via vms_changed

    assert page.bulk_storage_combo.currentData() == storage_b.uid


def test_bulk_assignment_is_one_undo_step():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_all_vms_storage()
    assert all(vm.storage_uid == storage.uid for vm in service.project.vms)

    service.undo()

    assert all(vm.storage_uid == "" for vm in service.project.vms)


# ----------------------------------------------------------------------
# Advanced Mode - Storage Pool is opt-in, like Cluster/VLAN
# ----------------------------------------------------------------------

def test_storage_widgets_and_column_hidden_by_default():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    assert page.storage_move_widgets.isVisible() is False
    assert page.table.isColumnHidden(13) is True


def test_storage_widgets_and_column_shown_when_advanced_enabled():
    service = ProjectService()
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    page.set_advanced_mode(True)
    QApplication.processEvents()

    assert page.storage_move_widgets.isVisible() is True
    assert page.table.isColumnHidden(13) is False


# ----------------------------------------------------------------------
# VMTableModel - the "Storage Pool" column itself
# ----------------------------------------------------------------------

def test_table_shows_assigned_storage_pool_name():
    from PySide6.QtCore import Qt
    from src.gui.models.vm_table_model import VMTableModel

    storage = Storage.create_default()
    storage.name = "SAN-Pool-1"
    vm = VirtualMachine.create_default()
    vm.storage_uid = storage.uid

    model = VMTableModel([vm], storages_provider=lambda: [storage])

    assert model.data(model.index(0, 13), Qt.ItemDataRole.DisplayRole) == "SAN-Pool-1"


def test_table_shows_dash_when_unassigned():
    from PySide6.QtCore import Qt
    from src.gui.models.vm_table_model import VMTableModel

    vm = VirtualMachine.create_default()
    model = VMTableModel([vm])

    assert model.data(model.index(0, 13), Qt.ItemDataRole.DisplayRole) == "-"


def test_table_shows_dash_for_stale_storage_reference():
    from PySide6.QtCore import Qt
    from src.gui.models.vm_table_model import VMTableModel

    vm = VirtualMachine.create_default()
    vm.storage_uid = "deleted-uid"
    model = VMTableModel([vm], storages_provider=lambda: [])

    assert model.data(model.index(0, 13), Qt.ItemDataRole.DisplayRole) == "-"
