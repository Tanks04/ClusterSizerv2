"""Real Qt tests for the Cluster dropdown on ServerDialog and VMDialog
- matches the exact pattern already established for Storage Pool/VLAN
assignment, including graceful fallback to (none) for a stale/deleted
reference."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.dialogs.vm_dialog import VMDialog
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# ServerDialog
# ----------------------------------------------------------------------

def test_server_dialog_no_clusters_shows_only_none():
    dialog = ServerDialog()
    assert dialog.cluster_combo.count() == 1
    assert dialog.cluster_combo.currentText() == "(none)"


def test_server_dialog_new_server_defaults_to_no_cluster():
    cluster = Cluster.create_default(0)
    dialog = ServerDialog(clusters=[cluster])

    server = dialog.get_server()

    assert server.cluster_uid == ""


def test_server_dialog_selecting_a_cluster_sets_cluster_uid():
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-A"
    dialog = ServerDialog(clusters=[cluster])

    dialog.cluster_combo.setCurrentIndex(1)
    server = dialog.get_server()

    assert server.cluster_uid == cluster.uid


def test_server_dialog_editing_preloads_assigned_cluster():
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-B"
    existing = Server.create_default()
    existing.cluster_uid = cluster.uid

    dialog = ServerDialog(existing, clusters=[cluster])

    assert "Cluster-B" in dialog.cluster_combo.currentText()


def test_server_dialog_stale_cluster_reference_falls_back_to_none():
    existing = Server.create_default()
    existing.cluster_uid = "deleted-uid"

    dialog = ServerDialog(existing, clusters=[])

    assert dialog.cluster_combo.currentIndex() == 0


def test_server_dialog_preserves_legacy_cluster_name_when_no_cluster_selected():
    """The free-text field is gone from the GUI, but its underlying
    model value (e.g. from an old import not yet linked to a
    structured Cluster) is preserved rather than blanked out."""
    server = Server.create_default()
    server.cluster_name = "vSAN_HPM"
    dialog = ServerDialog(server, clusters=[])

    result = dialog.get_server()

    assert result.cluster_name == "vSAN_HPM"
    assert result.cluster_uid == ""


def test_server_dialog_syncs_cluster_name_from_selected_cluster():
    """Selecting a structured Cluster keeps the legacy cluster_name
    field meaningful for anyone still reading/exporting it, instead of
    a separate manual text entry that could drift out of sync."""
    cluster = Cluster.create_default(0)
    cluster.name = "vSAN_HPM"
    server = Server.create_default()
    dialog = ServerDialog(server, clusters=[cluster])

    dialog.cluster_combo.setCurrentIndex(1)
    result = dialog.get_server()

    assert result.cluster_uid == cluster.uid
    assert result.cluster_name == "vSAN_HPM"


# ----------------------------------------------------------------------
# VMDialog
# ----------------------------------------------------------------------

def test_vm_dialog_no_clusters_shows_only_none():
    dialog = VMDialog()
    assert dialog.cluster_combo.count() == 1


def test_vm_dialog_selecting_a_cluster_sets_cluster_uid():
    cluster = Cluster.create_default(0)
    dialog = VMDialog(clusters=[cluster])

    dialog.cluster_combo.setCurrentIndex(1)
    vm = dialog.get_vm()

    assert vm.cluster_uid == cluster.uid


def test_vm_dialog_editing_preloads_assigned_cluster():
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-C"
    existing = VirtualMachine.create_default()
    existing.cluster_uid = cluster.uid

    dialog = VMDialog(existing, clusters=[cluster])

    assert "Cluster-C" in dialog.cluster_combo.currentText()


def test_vm_dialog_stale_cluster_reference_falls_back_to_none():
    existing = VirtualMachine.create_default()
    existing.cluster_uid = "deleted-uid"

    dialog = VMDialog(existing, clusters=[])

    assert dialog.cluster_combo.currentIndex() == 0
