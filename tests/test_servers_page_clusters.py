"""Real Qt tests for ServersPage's Clusters management section - Add/
Edit/Delete/Clear All for the Cluster entity, right above the main
servers table."""

import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.project_service import ProjectService
from src.gui.pages.servers_page import ServersPage
from src.gui.dialogs.cluster_dialog import ClusterDialog
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_add_cluster_via_dialog():
    service = ProjectService()
    page = ServersPage(service)
    new_cluster = Cluster.create_default(0)
    new_cluster.name = "Cluster-A"

    with patch.object(ClusterDialog, "exec", return_value=True), \
         patch.object(ClusterDialog, "get_cluster", return_value=new_cluster):
        page._add_cluster()

    assert len(service.project.clusters) == 1
    assert page.cluster_model.rowCount() == 1


def test_edit_cluster_requires_exactly_one_selected(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))

    service = ProjectService()
    service.add_cluster(Cluster.create_default(0))
    service.add_cluster(Cluster.create_default(1))
    page = ServersPage(service)
    page.cluster_table.selectAll()  # 2 selected, not exactly 1

    page._edit_cluster()

    assert informed.get("called") is True


def test_edit_cluster_updates_the_selected_one():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = ServersPage(service)
    page.cluster_table.selectRow(0)

    updated = Cluster(uid=cluster.uid, name="Renamed", site="Primary", color="#000000")
    with patch.object(ClusterDialog, "exec", return_value=True), \
         patch.object(ClusterDialog, "get_cluster", return_value=updated):
        page._edit_cluster()

    assert service.project.clusters[0].name == "Renamed"


def test_delete_clusters_cascades_and_confirms():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)
    page = ServersPage(service)
    page.cluster_table.selectAll()

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._delete_clusters()

    assert service.project.clusters == []
    assert service.project.servers[0].cluster_uid == ""


def test_delete_clusters_with_no_selection_shows_a_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))

    service = ProjectService()
    page = ServersPage(service)

    page._delete_clusters()

    assert informed.get("called") is True


def test_clear_all_clusters():
    service = ProjectService()
    service.add_cluster(Cluster.create_default(0))
    service.add_cluster(Cluster.create_default(1))
    page = ServersPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._clear_clusters()

    assert service.project.clusters == []


def test_cluster_table_refreshes_when_a_server_is_assigned():
    from PySide6.QtCore import Qt

    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = ServersPage(service)
    assert page.cluster_model.data(page.cluster_model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "0"

    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)

    assert page.cluster_model.data(page.cluster_model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "1"
