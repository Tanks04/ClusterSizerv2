"""Real Qt tests for spinbox step sizes on RAM/disk-capacity fields -
requested directly: RAM should step by 32GB (a single DIMM increment,
not the previous 1024GB which was too coarse for fine adjustment), and
TB-denominated disk capacity fields should step by 1TB."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.dialogs.storage_dialog import StorageDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_server_ram_step_is_one_dimm_increment():
    dialog = ServerDialog()
    assert dialog.ram_spin.singleStep() == 32


def test_server_local_disk_step_is_one_terabyte():
    dialog = ServerDialog()
    assert dialog.local_disk_spin.singleStep() == 1.0


def test_storage_raw_capacity_step_is_one_terabyte():
    dialog = StorageDialog(servers=[])
    assert dialog.raw_spin.singleStep() == 1.0


def test_storage_usable_capacity_step_is_one_terabyte():
    dialog = StorageDialog(servers=[])
    assert dialog.usable_spin.singleStep() == 1.0
