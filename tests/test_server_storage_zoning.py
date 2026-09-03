"""Real Qt tests for bulk-assigning servers to a Storage array's
zoning (Storage.server_uids) - moved here from the VMs tab, since
zoning is fundamentally a server/host concept (which hosts a storage
array is presented to), not a VM one. Also covers the Cluster-based
shortcut: assigning a whole cluster's current member servers at once.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.storage_dialog import StorageDialog
from src.gui.pages.servers_page import ServersPage
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.storage import Storage
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _servers(service, count=3, cluster_uid=""):
    servers = []
    for i in range(count):
        s = Server.create_default()
        s.name = f"esxi-{i}"
        s.cluster_uid = cluster_uid
        service.add_server(s)
        servers.append(s)
    return servers


# ----------------------------------------------------------------------
# ProjectService.add_servers_to_storage_zoning
# ----------------------------------------------------------------------

def test_zoning_is_additive():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)

    service.add_servers_to_storage_zoning(storage.uid, ["a", "b"])
    service.add_servers_to_storage_zoning(storage.uid, ["b", "c"])

    assert service.project.storages[0].server_uids == ["a", "b", "c"]


def test_zoning_unknown_storage_uid_does_nothing():
    service = ProjectService()

    service.add_servers_to_storage_zoning("does-not-exist", ["a"])

    assert service.project.storages == []


def test_zoning_is_one_undo_step():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)

    service.add_servers_to_storage_zoning(storage.uid, ["a", "b", "c"])
    service.undo()

    assert service.project.storages[0].server_uids == []


# ----------------------------------------------------------------------
# ServersPage - the three bulk-assign paths
# ----------------------------------------------------------------------

def test_zone_storage_combo_populated():
    service = ProjectService()
    storage = Storage.create_default()
    storage.name = "SAN01"
    service.add_storage(storage)

    page = ServersPage(service)

    assert page.zone_storage_combo.count() == 1
    assert page.zone_storage_combo.currentText() == "SAN01"


def test_zone_cluster_combo_populated():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    cluster.name = "ProdCluster"
    service.add_cluster(cluster)

    page = ServersPage(service)

    assert page.zone_cluster_combo.count() == 1
    assert page.zone_cluster_combo.currentText() == "ProdCluster"


def test_zone_selected_servers():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    servers = _servers(service, 3)
    page = ServersPage(service)
    page.table.selectRow(0)

    page._zone_storage_to_selected_servers()

    assert service.project.storages[0].server_uids == [servers[0].uid]


def test_zone_selected_with_no_selection_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _servers(service, 3)
    page = ServersPage(service)

    page._zone_storage_to_selected_servers()

    assert informed.get("called") is True


def test_zone_selected_with_no_storage_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    _servers(service, 3)
    page = ServersPage(service)
    page.table.selectRow(0)

    page._zone_storage_to_selected_servers()

    assert informed.get("called") is True


def test_zone_all_servers():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    servers = _servers(service, 3)
    page = ServersPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._zone_storage_to_all_servers()

    assert set(service.project.storages[0].server_uids) == {s.uid for s in servers}


def test_zone_all_cancelled_changes_nothing():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    _servers(service, 3)
    page = ServersPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        page._zone_storage_to_all_servers()

    assert service.project.storages[0].server_uids == []


def test_zone_to_cluster_expands_to_current_members_only():
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    in_cluster = _servers(service, 2, cluster_uid=cluster.uid)
    outside = _servers(service, 1)  # not in the cluster
    page = ServersPage(service)

    page._zone_storage_to_cluster_servers()

    assigned = set(service.project.storages[0].server_uids)
    assert assigned == {s.uid for s in in_cluster}
    assert outside[0].uid not in assigned


def test_zone_to_cluster_with_no_members_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = ServersPage(service)

    page._zone_storage_to_cluster_servers()

    assert informed.get("called") is True


def test_zone_to_cluster_is_a_one_time_snapshot_not_a_standing_link():
    """Adding a NEW server to the cluster AFTER the cascade must not
    retroactively appear in the storage's zoning - it's a one-time
    starting point, not an ongoing sync."""
    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    original = _servers(service, 1, cluster_uid=cluster.uid)
    page = ServersPage(service)
    page._zone_storage_to_cluster_servers()

    new_member = Server.create_default()
    new_member.cluster_uid = cluster.uid
    service.add_server(new_member)

    assert new_member.uid not in service.project.storages[0].server_uids
    assert original[0].uid in service.project.storages[0].server_uids


def test_zoning_can_be_manually_removed_afterward():
    """Confirms the "remove individual servers manually later" half of
    the workflow - StorageDialog can still edit server_uids down."""
    service = ProjectService()
    s1 = Server.create_default()
    s2 = Server.create_default()
    service.add_server(s1)
    service.add_server(s2)
    storage = Storage.create_default()
    storage.server_uids = [s1.uid, s2.uid]
    service.add_storage(storage)

    storage.server_uids.remove(s1.uid)

    assert service.project.storages[0].server_uids == [s2.uid]


# ----------------------------------------------------------------------
# StorageDialog - server_uids preserved through edits (same bug class
# as cluster_name/disk_count/raid_level caught earlier)
# ----------------------------------------------------------------------

def test_storage_dialog_preserves_server_uids_on_edit():
    service = ProjectService()
    s1 = Server.create_default()
    s2 = Server.create_default()
    service.add_server(s1)
    service.add_server(s2)
    storage = Storage.create_default()
    storage.server_uids = [s1.uid, s2.uid]
    service.add_storage(storage)

    dialog = StorageDialog(storage, servers=[s1, s2], service=service)
    result = dialog.get_storage()

    assert result.server_uids == [s1.uid, s2.uid]


def test_new_storage_starts_with_no_server_uids():
    dialog = StorageDialog(servers=[])

    storage = dialog.get_storage()

    assert storage.server_uids == []
