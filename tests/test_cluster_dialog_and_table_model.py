"""Real Qt tests for ClusterDialog (add/edit with a color picker) and
ClusterTableModel (colored badge, server/VM counts, per-cluster
utilization with the same warning markers as the Storage Pool table
column)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.gui.dialogs.cluster_dialog import ClusterDialog
from src.gui.models.cluster_table_model import ClusterTableModel
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.calculations.thresholds import Thresholds


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _data(model, row, col, role=Qt.ItemDataRole.DisplayRole):
    return model.data(model.index(row, col), role)


# ----------------------------------------------------------------------
# ClusterDialog
# ----------------------------------------------------------------------

def test_new_cluster_dialog_defaults():
    dialog = ClusterDialog(sites=["Primary", "DR"], default_color="#e57373")

    cluster = dialog.get_cluster()

    assert cluster.name == ""
    assert cluster.color == "#e57373"


def test_cluster_dialog_captures_entered_values():
    dialog = ClusterDialog(sites=["Primary", "DR", "DR2"])
    dialog.name_edit.setText("Cluster-A")
    dialog.site_combo.setCurrentText("DR2")
    dialog.notes_edit.setPlainText("Isolated failure domain")

    cluster = dialog.get_cluster()

    assert cluster.name == "Cluster-A"
    assert cluster.site == "DR2"
    assert cluster.notes == "Isolated failure domain"


def test_editing_preloads_existing_values():
    existing = Cluster.create_default(0)
    existing.name = "Existing"
    existing.color = "#4db6ac"

    dialog = ClusterDialog(existing, sites=["Primary", "DR"])

    assert dialog.name_edit.text() == "Existing"
    assert dialog._color == "#4db6ac"
    updated = dialog.get_cluster()
    assert updated.uid == existing.uid


# ----------------------------------------------------------------------
# ClusterTableModel
# ----------------------------------------------------------------------

def test_color_shown_as_background():
    cluster = Cluster.create_default(0)
    cluster.color = "#e57373"
    model = ClusterTableModel([cluster])

    bg = model.data(model.index(0, 2), Qt.ItemDataRole.BackgroundRole)

    assert bg == QColor("#e57373")


def test_server_and_vm_counts():
    cluster = Cluster.create_default(0)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    vm1 = VirtualMachine.create_default()
    vm1.cluster_uid = cluster.uid
    vm2 = VirtualMachine.create_default()
    vm2.cluster_uid = cluster.uid

    model = ClusterTableModel([cluster], servers_provider=lambda: [server], vms_provider=lambda: [vm1, vm2])

    assert _data(model, 0, 3) == "1"
    assert _data(model, 0, 4) == "2"


def test_unassigned_entities_not_counted():
    cluster = Cluster.create_default(0)
    other_server = Server.create_default()  # cluster_uid left empty

    model = ClusterTableModel([cluster], servers_provider=lambda: [other_server])

    assert _data(model, 0, 3) == "0"


def test_cpu_ratio_dash_when_no_servers():
    cluster = Cluster.create_default(0)
    model = ClusterTableModel([cluster])

    assert _data(model, 0, 5) == "-"


def test_oversubscribed_cluster_shows_warning_marker_and_color():
    cluster = Cluster.create_default(0)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    server.sockets = 1
    server.cores_per_socket = 8
    server.hyperthreading_enabled = False
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid
    vm.vcpu = 64

    model = ClusterTableModel(
        [cluster], servers_provider=lambda: [server], vms_provider=lambda: [vm],
        thresholds_provider=Thresholds,
    )

    text = _data(model, 0, 5)
    assert "\u26a0" in text
    assert model.data(model.index(0, 5), Qt.ItemDataRole.ForegroundRole) is not None


def test_healthy_cluster_shows_no_warning():
    cluster = Cluster.create_default(0)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    server.sockets = 2
    server.cores_per_socket = 32
    server.hyperthreading_enabled = False
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid
    vm.vcpu = 8

    model = ClusterTableModel(
        [cluster], servers_provider=lambda: [server], vms_provider=lambda: [vm],
        thresholds_provider=Thresholds,
    )

    text = _data(model, 0, 5)
    assert "\u26a0" not in text
    assert model.data(model.index(0, 5), Qt.ItemDataRole.ForegroundRole) is None
