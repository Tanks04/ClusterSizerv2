"""Real Qt tests for the Storage dialog's HCI checkbox list - now that
PySide6 is actually installed in this environment (it wasn't for most
of this project's development, which relied on static source-inspection
tests instead). Pins a real bug found here: a fresh "Add Storage"
dialog never populated the server list at all when HCI was checked -
only load() (the "Edit" path) did, via _populate_hci_server_list()."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.models.server import Server
from src.gui.dialogs.storage_dialog import StorageDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _servers():
    s1 = Server.create_default()
    s1.name = "esxi-01"
    s1.local_disk_raw_tb = 30.0
    s2 = Server.create_default()
    s2.name = "esxi-02"
    s2.local_disk_raw_tb = 30.0
    s3 = Server.create_default()
    s3.name = "esxi-03"
    s3.local_disk_raw_tb = 30.0
    return [s1, s2, s3]


def test_new_storage_dialog_populates_server_list_on_hci_toggle():
    """Pins the bug: a fresh Add-Storage dialog (no load() call) must
    still populate the checkbox list the first time HCI is checked."""
    servers = _servers()
    dialog = StorageDialog(servers=servers)

    assert dialog.hci_servers_list.count() == 0  # not populated yet

    dialog.is_hci_check.setChecked(True)

    assert dialog.hci_servers_list.count() == 3


def test_checking_servers_recomputes_raw_capacity_live():
    servers = _servers()
    dialog = StorageDialog(servers=servers)
    dialog.is_hci_check.setChecked(True)

    dialog.hci_servers_list.item(0).setCheckState(Qt.CheckState.Checked)
    dialog.hci_servers_list.item(1).setCheckState(Qt.CheckState.Checked)
    assert dialog.raw_spin.value() == 60.0

    dialog.hci_servers_list.item(2).setCheckState(Qt.CheckState.Checked)
    assert dialog.raw_spin.value() == 90.0


def test_raw_capacity_field_is_read_only_while_hci_is_checked():
    dialog = StorageDialog(servers=_servers())
    dialog.is_hci_check.setChecked(True)
    assert dialog.raw_spin.isReadOnly() is True

    dialog.is_hci_check.setChecked(False)
    assert dialog.raw_spin.isReadOnly() is False


def test_toggling_hci_off_and_back_on_preserves_checked_servers():
    """The populate-on-first-toggle guard is keyed on the list being
    empty - re-toggling within one session must not wipe selections."""
    dialog = StorageDialog(servers=_servers())
    dialog.is_hci_check.setChecked(True)
    for i in range(3):
        dialog.hci_servers_list.item(i).setCheckState(Qt.CheckState.Checked)

    dialog.is_hci_check.setChecked(False)
    dialog.is_hci_check.setChecked(True)

    checked = sum(
        1 for i in range(dialog.hci_servers_list.count())
        if dialog.hci_servers_list.item(i).checkState() == Qt.CheckState.Checked
    )
    assert checked == 3


def test_get_storage_returns_correct_hci_state():
    servers = _servers()
    dialog = StorageDialog(servers=servers)
    dialog.is_hci_check.setChecked(True)
    for i in range(3):
        dialog.hci_servers_list.item(i).setCheckState(Qt.CheckState.Checked)

    storage = dialog.get_storage()

    assert storage.is_hci is True
    assert storage.raw_capacity_tb == 90.0
    assert set(storage.hci_server_uids) == {s.uid for s in servers}


def test_editing_existing_hci_storage_preloads_checked_servers():
    from src.models.storage import Storage

    servers = _servers()
    existing = Storage.create_default()
    existing.is_hci = True
    existing.hci_server_uids = [servers[0].uid, servers[1].uid]
    existing.raw_capacity_tb = 60.0

    dialog = StorageDialog(existing, servers=servers)

    assert dialog.is_hci_check.isChecked() is True
    checked_names = {
        dialog.hci_servers_list.item(i).text().split(" (")[0]
        for i in range(dialog.hci_servers_list.count())
        if dialog.hci_servers_list.item(i).checkState() == Qt.CheckState.Checked
    }
    assert checked_names == {"esxi-01", "esxi-02"}
