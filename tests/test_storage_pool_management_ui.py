"""Real Qt tests for the Storage Pools management section embedded in
StorageDialog - Add/Edit/Delete for carving one array into several
pools, each optionally zoned to specific servers. Mirrors the existing
Expansion Shelves section's structure (a mini table + buttons within
the dialog), but pools need a full sub-dialog (StoragePoolDialog)
since a server checklist doesn't fit in a table cell.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.storage_dialog import StorageDialog
from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog
from src.models.server import Server
from src.models.storage import Storage, StoragePool


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_new_storage_has_empty_pools_table():
    dialog = StorageDialog(servers=[])

    assert dialog.pools_table.rowCount() == 0


def test_add_pool_via_dialog():
    dialog = StorageDialog(servers=[])
    new_pool = StoragePool(uid="p1", name="SSD-Tier", raw_capacity_tb=20.0, usable_capacity_tb=15.0)

    with patch.object(StoragePoolDialog, "exec", return_value=True), \
         patch.object(StoragePoolDialog, "get_pool", return_value=new_pool):
        dialog._add_pool()

    assert len(dialog._pools) == 1
    assert dialog.pools_table.rowCount() == 1
    assert dialog.pools_table.item(0, 0).text() == "SSD-Tier"
    assert dialog.pools_table.item(0, 1).text() == "20"
    assert dialog.pools_table.item(0, 2).text() == "15"


def test_add_pool_cancelled_adds_nothing():
    dialog = StorageDialog(servers=[])

    with patch.object(StoragePoolDialog, "exec", return_value=False):
        dialog._add_pool()

    assert dialog._pools == []
    assert dialog.pools_table.rowCount() == 0


def test_edit_pool_requires_exactly_one_selected(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    dialog = StorageDialog(servers=[])
    dialog._pools = [StoragePool(uid="p1", name="A"), StoragePool(uid="p2", name="B")]
    dialog._refresh_pools_table()
    dialog.pools_table.selectAll()

    dialog._edit_pool()

    assert informed.get("called") is True


def test_edit_pool_updates_the_selected_one():
    dialog = StorageDialog(servers=[])
    dialog._pools = [StoragePool(uid="p1", name="Original")]
    dialog._refresh_pools_table()
    dialog.pools_table.selectRow(0)

    updated = StoragePool(uid="p1", name="Renamed", raw_capacity_tb=99.0)
    with patch.object(StoragePoolDialog, "exec", return_value=True), \
         patch.object(StoragePoolDialog, "get_pool", return_value=updated):
        dialog._edit_pool()

    assert dialog._pools[0].name == "Renamed"
    assert dialog.pools_table.item(0, 0).text() == "Renamed"


def test_remove_selected_pool():
    dialog = StorageDialog(servers=[])
    dialog._pools = [StoragePool(uid="p1", name="A"), StoragePool(uid="p2", name="B")]
    dialog._refresh_pools_table()
    dialog.pools_table.selectRow(0)

    dialog._remove_selected_pool()

    assert len(dialog._pools) == 1
    assert dialog._pools[0].name == "B"
    assert dialog.pools_table.rowCount() == 1


def test_pools_persist_through_get_storage():
    dialog = StorageDialog(servers=[])
    new_pool = StoragePool(uid="p1", name="SSD-Tier", raw_capacity_tb=20.0)
    with patch.object(StoragePoolDialog, "exec", return_value=True), \
         patch.object(StoragePoolDialog, "get_pool", return_value=new_pool):
        dialog._add_pool()

    storage = dialog.get_storage()

    assert len(storage.pools) == 1
    assert storage.pools[0].name == "SSD-Tier"


def test_existing_pools_load_into_the_table():
    server = Server.create_default()
    existing = Storage.create_default()
    pool1 = StoragePool(uid="p1", name="SSD-Tier", raw_capacity_tb=20.0, usable_capacity_tb=15.0, server_uids=[server.uid])
    pool2 = StoragePool(uid="p2", name="SATA-Tier", raw_capacity_tb=40.0, usable_capacity_tb=32.0)
    existing.pools = [pool1, pool2]

    dialog = StorageDialog(existing, servers=[server])

    assert dialog.pools_table.rowCount() == 2
    assert dialog.pools_table.item(0, 0).text() == "SSD-Tier"
    assert dialog.pools_table.item(0, 3).text() == "1"
    assert dialog.pools_table.item(1, 0).text() == "SATA-Tier"
    assert dialog.pools_table.item(1, 3).text() == "0"


# ----------------------------------------------------------------------
# StoragePoolDialog itself
# ----------------------------------------------------------------------

def test_pool_dialog_new_pool_gets_a_generated_uid():
    dialog = StoragePoolDialog(servers=[])
    dialog.name_edit.setText("SSD-Tier")

    pool = dialog.get_pool()

    assert pool.uid
    assert pool.name == "SSD-Tier"


def test_pool_dialog_editing_keeps_the_same_uid():
    existing = StoragePool(uid="p1", name="SSD-Tier")

    dialog = StoragePoolDialog(existing, servers=[])
    result = dialog.get_pool()

    assert result.uid == "p1"


def test_pool_dialog_server_checklist_reflects_pool_assignment():
    srv1 = Server.create_default()
    srv1.name = "esxi-01"
    srv2 = Server.create_default()
    srv2.name = "esxi-02"
    existing = StoragePool(uid="p1", name="SSD-Tier", server_uids=[srv2.uid])

    dialog = StoragePoolDialog(existing, servers=[srv1, srv2])
    result = dialog.get_pool()

    assert result.server_uids == [srv2.uid]


def test_pool_dialog_notes_round_trip():
    dialog = StoragePoolDialog(servers=[])
    dialog.notes_edit.setPlainText("Fast tier for databases")

    pool = dialog.get_pool()

    assert pool.notes == "Fast tier for databases"


def test_pools_table_shows_utilization_with_service():
    from src.models.virtual_machine import VirtualMachine
    from src.services.project_service import ProjectService

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="SSD-Tier", usable_capacity_tb=1.0)
    storage.pools = [pool]
    service.add_storage(storage)
    vm = VirtualMachine.create_default()
    vm.disk_gb = 512
    vm.storage_uid = storage.uid
    vm.storage_pool_uid = "p1"
    service.add_vm(vm)

    dialog = StorageDialog(storage, servers=[], service=service)

    assert dialog.pools_table.item(0, 4).text() == "50%"


def test_pools_table_shows_dash_without_service():
    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="SSD-Tier", usable_capacity_tb=1.0)]

    dialog = StorageDialog(storage, servers=[])

    assert dialog.pools_table.item(0, 4).text() == "-"
