"""Real Qt test for ServerTableModel's Effective Cores column - shown
as a dash when Hyperthreading is off, since it's otherwise identical
to Total Cores and just adds redundant, confusing noise. Reported
directly."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.models.server_table_model import ServerTableModel
from src.models.server import Server


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_effective_cores_shown_when_ht_enabled():
    server = Server.create_default()
    server.hyperthreading_enabled = True
    server.sockets = 2
    server.cores_per_socket = 16
    server.threads_per_core = 2

    model = ServerTableModel([server])

    assert model.data(model.index(0, 11), Qt.ItemDataRole.DisplayRole) == 64


def test_effective_cores_is_dash_when_ht_disabled():
    server = Server.create_default()
    server.hyperthreading_enabled = False
    server.sockets = 2
    server.cores_per_socket = 16

    model = ServerTableModel([server])

    assert model.data(model.index(0, 11), Qt.ItemDataRole.DisplayRole) == "-"
