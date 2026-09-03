"""Real Qt tests for the structured "Cluster" column on ServerTableModel
and VMTableModel - a colored badge (BackgroundRole) showing the linked
Cluster entity's color. Server's free-text "Cluster Name" was removed
from the GUI entirely (consolidated into this one structured column -
RVTools/CSV import now auto-creates/links a real Cluster from it
instead of leaving it as a separate, confusing field)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.gui.models.server_table_model import ServerTableModel
from src.gui.models.vm_table_model import VMTableModel
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _data(model, row, col, role=Qt.ItemDataRole.DisplayRole):
    return model.data(model.index(row, col), role)


# ----------------------------------------------------------------------
# ServerTableModel
# ----------------------------------------------------------------------

def test_server_cluster_name_column_no_longer_exists():
    model = ServerTableModel()

    assert "Cluster Name" not in model.HEADERS
    assert model.HEADERS[16] == "Cluster"


def test_server_cluster_column_shows_name_and_colored_background():
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-A"
    cluster.color = "#4db6ac"
    server = Server.create_default()
    server.cluster_uid = cluster.uid

    model = ServerTableModel([server], clusters_provider=lambda: [cluster])

    assert _data(model, 0, 16) == "Cluster-A"
    assert _data(model, 0, 16, Qt.ItemDataRole.BackgroundRole) == QColor("#4db6ac")


def test_server_unassigned_shows_dash_and_no_background():
    server = Server.create_default()
    model = ServerTableModel([server])

    assert _data(model, 0, 16) == "-"
    assert _data(model, 0, 16, Qt.ItemDataRole.BackgroundRole) is None


def test_server_stale_cluster_reference_shows_dash():
    server = Server.create_default()
    server.cluster_uid = "deleted-uid"
    model = ServerTableModel([server], clusters_provider=lambda: [])

    assert _data(model, 0, 16) == "-"


def test_server_editable_columns_unaffected_by_column_shift():
    """Sockets/Cores/Threads/RAM/GHz/Rack/Power stay editable after
    Cluster Name's removal shifted indices 18-19 down to 17-18."""
    model = ServerTableModel()
    assert model.EDITABLE_COLUMNS == {6, 7, 8, 12, 13, 17, 18}


# ----------------------------------------------------------------------
# VMTableModel
# ----------------------------------------------------------------------

def test_vm_cluster_column_shows_name_and_color():
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-B"
    cluster.color = "#64b5f6"
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid

    model = VMTableModel([vm], clusters_provider=lambda: [cluster])

    assert model.HEADERS[12] == "Cluster"
    assert model.HEADERS[14] == "Notes"
    assert _data(model, 0, 12) == "Cluster-B"
    assert _data(model, 0, 12, Qt.ItemDataRole.BackgroundRole) == QColor("#64b5f6")


def test_vm_unassigned_shows_dash_and_no_background():
    vm = VirtualMachine.create_default()
    model = VMTableModel([vm])

    assert _data(model, 0, 12) == "-"
    assert _data(model, 0, 12, Qt.ItemDataRole.BackgroundRole) is None


def test_vm_stale_cluster_reference_shows_dash():
    vm = VirtualMachine.create_default()
    vm.cluster_uid = "deleted-uid"
    model = VMTableModel([vm], clusters_provider=lambda: [])

    assert _data(model, 0, 12) == "-"


def test_vm_notes_column_unaffected_by_shift():
    vm = VirtualMachine.create_default()
    vm.notes = "some notes"
    model = VMTableModel([vm])

    assert _data(model, 0, 14) == "some notes"


def test_vm_editable_columns_unaffected_by_column_shift():
    model = VMTableModel()
    assert model.EDITABLE_COLUMNS == {2, 4, 5}


# ----------------------------------------------------------------------
# Full page integration - live refresh on reassignment
# ----------------------------------------------------------------------

def test_servers_page_cluster_column_live_refreshes():
    from src.gui.pages.servers_page import ServersPage
    from src.services.project_service import ProjectService

    service = ProjectService()
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-A"
    service.add_cluster(cluster)
    server = Server.create_default()
    service.add_server(server)
    page = ServersPage(service)
    assert _data(page.model, 0, 16) == "-"

    server.cluster_uid = cluster.uid
    service.touch_servers()

    assert _data(page.model, 0, 16) == "Cluster-A"


def test_vms_page_cluster_column_live_refreshes():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage
    from src.services.project_service import ProjectService

    service = ProjectService()
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-A"
    service.add_cluster(cluster)
    vm = VirtualMachine.create_default()
    service.add_vm(vm)
    page = VirtualMachinesPage(service)
    assert _data(page.model, 0, 12) == "-"

    vm.cluster_uid = cluster.uid
    service.touch_vms()

    assert _data(page.model, 0, 12) == "Cluster-A"
