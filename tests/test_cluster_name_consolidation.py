"""Tests for consolidating Server's free-text cluster_name and the
structured Cluster entity into one concept in the GUI - reported
directly as confusing to have both. RVTools and CSV import now
auto-create/link a real, colored Cluster from the imported name
instead of leaving it as a dead-end text field.
"""

import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.models.cluster import Cluster, find_or_create_clusters_by_name
from src.models.server import Server
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _server(site="Primary", cluster_name=""):
    s = Server.create_default()
    s.site = site
    s.cluster_name = cluster_name
    return s


# ----------------------------------------------------------------------
# find_or_create_clusters_by_name
# ----------------------------------------------------------------------

def test_groups_servers_by_site_and_name():
    servers = [_server(cluster_name="vSAN_HPM") for _ in range(3)]
    servers.append(_server(cluster_name="vSAN_Edge"))

    new_clusters = find_or_create_clusters_by_name([], servers)

    assert len(new_clusters) == 2
    assert servers[0].cluster_uid == servers[1].cluster_uid == servers[2].cluster_uid
    assert servers[3].cluster_uid != servers[0].cluster_uid


def test_same_name_different_site_gets_separate_clusters():
    servers = [_server(site="Primary", cluster_name="core"), _server(site="DR", cluster_name="core")]

    new_clusters = find_or_create_clusters_by_name([], servers)

    assert len(new_clusters) == 2
    assert servers[0].cluster_uid != servers[1].cluster_uid


def test_reuses_an_existing_cluster_by_name_instead_of_duplicating():
    existing = Cluster.create_default(0)
    existing.name = "vSAN_HPM"
    existing.site = "Primary"
    servers = [_server(cluster_name="vSAN_HPM")]

    new_clusters = find_or_create_clusters_by_name([existing], servers)

    assert new_clusters == []
    assert servers[0].cluster_uid == existing.uid


def test_blank_cluster_name_creates_nothing():
    servers = [_server(cluster_name="")]

    new_clusters = find_or_create_clusters_by_name([], servers)

    assert new_clusters == []
    assert servers[0].cluster_uid == ""


def test_new_clusters_get_colors_from_the_rotation():
    servers = [_server(cluster_name="a"), _server(cluster_name="b")]

    new_clusters = find_or_create_clusters_by_name([], servers)

    assert new_clusters[0].color != new_clusters[1].color


# ----------------------------------------------------------------------
# CSV import wiring (ProjectService.import_servers_csv)
# ----------------------------------------------------------------------

def test_csv_import_auto_creates_cluster_from_name(tmp_path):
    service = ProjectService()
    path = tmp_path / "servers.csv"
    path.write_text(
        "name,site,sockets,cores_per_socket,cluster_name\n"
        "esxi-1,Primary,2,16,vSAN_HPM\n"
        "esxi-2,Primary,2,16,vSAN_HPM\n"
        "esxi-3,Primary,2,16,\n",
        encoding="utf-8",
    )

    service.import_servers_csv(path)

    assert len(service.project.clusters) == 1
    assert service.project.clusters[0].name == "vSAN_HPM"
    assert service.project.servers[0].cluster_uid == service.project.servers[1].cluster_uid
    assert service.project.servers[2].cluster_uid == ""


def test_csv_import_reuses_existing_cluster_on_reimport(tmp_path):
    service = ProjectService()
    existing = Cluster.create_default(0)
    existing.name = "vSAN_HPM"
    existing.site = "Primary"
    service.add_cluster(existing)
    path = tmp_path / "servers.csv"
    path.write_text(
        "name,site,sockets,cores_per_socket,cluster_name\nesxi-4,Primary,2,16,vSAN_HPM\n",
        encoding="utf-8",
    )

    service.import_servers_csv(path)

    assert len(service.project.clusters) == 1  # no duplicate
    assert service.project.servers[0].cluster_uid == existing.uid


def test_csv_import_cluster_creation_is_one_undo_step(tmp_path):
    service = ProjectService()
    path = tmp_path / "servers.csv"
    path.write_text(
        "name,site,sockets,cores_per_socket,cluster_name\nesxi-1,Primary,2,16,vSAN_HPM\n",
        encoding="utf-8",
    )

    service.import_servers_csv(path)
    assert len(service.project.clusters) == 1

    service.undo()

    assert service.project.clusters == []
    assert service.project.servers == []


# ----------------------------------------------------------------------
# RVTools import wiring (MainWindow._import_rvtools)
# ----------------------------------------------------------------------

def test_rvtools_import_auto_creates_cluster():
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)
    s1 = _server(cluster_name="vSAN_HPM")
    s2 = _server(cluster_name="vSAN_HPM")

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1
    mock_dialog.get_servers.return_value = [s1, s2]
    mock_dialog.get_vms.return_value = []
    mock_dialog.get_switches.return_value = []

    with patch("src.gui.main_window.RVToolsImportDialog", return_value=mock_dialog), \
         patch.object(QMessageBox, "information"):
        window._import_rvtools()

    assert len(service.project.clusters) == 1
    assert service.project.clusters[0].name == "vSAN_HPM"
    assert service.project.servers[0].cluster_uid == service.project.servers[1].cluster_uid


def test_rvtools_import_undo_reverts_servers_and_new_cluster_together():
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1
    mock_dialog.get_servers.return_value = [_server(cluster_name="vSAN_HPM")]
    mock_dialog.get_vms.return_value = []
    mock_dialog.get_switches.return_value = []

    with patch("src.gui.main_window.RVToolsImportDialog", return_value=mock_dialog), \
         patch.object(QMessageBox, "information"):
        window._import_rvtools()
    assert len(service.project.clusters) == 1

    service.undo()

    assert service.project.clusters == []
    assert service.project.servers == []


# ----------------------------------------------------------------------
# ServerDialog no longer shows a separate free-text field
# ----------------------------------------------------------------------

def test_server_dialog_has_no_separate_cluster_name_widget():
    from src.gui.dialogs.server_dialog import ServerDialog

    dialog = ServerDialog()

    assert not hasattr(dialog, "cluster_name_edit")


def test_server_table_has_only_one_cluster_column():
    from src.gui.models.server_table_model import ServerTableModel

    model = ServerTableModel()

    assert model.HEADERS.count("Cluster") == 1
    assert "Cluster Name" not in model.HEADERS
