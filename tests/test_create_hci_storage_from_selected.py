"""Real Qt tests for ServersPage's "Create HCI Storage from Selected"
right-click action - the confirmed UX for "when a server is marked
HCI, immediately create storage": since is_hci actually lives on the
Storage entity (not Server), this creates a new Storage linking the
selected servers, with Raw auto-computed and Usable left for the
person to set (with the FTT calculator now available)."""

import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog

from src.services.project_service import ProjectService
from src.gui.pages.servers_page import ServersPage
from src.models.server import Server
from src.models.cluster_project import PRIMARY, DR


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _server(site=PRIMARY, local_disk_raw_tb=12.0, cluster_name=""):
    s = Server.create_default()
    s.site = site
    s.local_disk_raw_tb = local_disk_raw_tb
    s.cluster_name = cluster_name
    return s


def test_creates_hci_storage_linking_all_selected_servers():
    service = ProjectService()
    for _ in range(4):
        service.add_server(_server())
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("My HCI Storage", True)), \
         patch.object(QMessageBox, "information"):
        page._create_hci_storage_from_selected()

    assert len(service.project.storages) == 1
    storage = service.project.storages[0]
    assert storage.is_hci is True
    assert storage.name == "My HCI Storage"
    assert len(storage.hci_server_uids) == 4


def test_raw_capacity_auto_computed_from_linked_servers():
    service = ProjectService()
    for _ in range(4):
        service.add_server(_server(local_disk_raw_tb=12.0))
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("Storage", True)), \
         patch.object(QMessageBox, "information"):
        page._create_hci_storage_from_selected()

    assert service.project.storages[0].raw_capacity_tb == 48.0


def test_usable_left_at_zero_for_manual_or_ftt_calculator_followup():
    service = ProjectService()
    service.add_server(_server())
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("Storage", True)), \
         patch.object(QMessageBox, "information"):
        page._create_hci_storage_from_selected()

    assert service.project.storages[0].usable_capacity_tb == 0.0


def test_storage_site_matches_the_selected_servers():
    service = ProjectService()
    service.add_server(_server(site=DR))
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("Storage", True)), \
         patch.object(QMessageBox, "information"):
        page._create_hci_storage_from_selected()

    assert service.project.storages[0].site == DR


def test_default_name_uses_cluster_name_when_set():
    service = ProjectService()
    service.add_server(_server(cluster_name="vSAN-Prod"))
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText") as mock_get_text, \
         patch.object(QMessageBox, "information"):
        mock_get_text.return_value = ("vSAN-Prod HCI Storage", True)
        page._create_hci_storage_from_selected()

    default_text_arg = mock_get_text.call_args[1].get("text") or mock_get_text.call_args[0][3]
    assert "vSAN-Prod" in default_text_arg


def test_servers_spanning_multiple_sites_is_blocked():
    service = ProjectService()
    service.add_server(_server(site=PRIMARY))
    service.add_server(_server(site=DR))
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QMessageBox, "warning") as mock_warn:
        page._create_hci_storage_from_selected()

    assert mock_warn.called
    assert service.project.storages == []


def test_no_selection_shows_a_message():
    service = ProjectService()
    page = ServersPage(service)

    with patch.object(QMessageBox, "information") as mock_info:
        page._create_hci_storage_from_selected()

    assert mock_info.called
    assert service.project.storages == []


def test_cancelling_the_name_prompt_creates_nothing():
    service = ProjectService()
    service.add_server(_server())
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("", False)):
        page._create_hci_storage_from_selected()

    assert service.project.storages == []


def test_creation_is_undoable():
    service = ProjectService()
    service.add_server(_server())
    page = ServersPage(service)
    page.table.selectAll()

    with patch.object(QInputDialog, "getText", return_value=("Storage", True)), \
         patch.object(QMessageBox, "information"):
        page._create_hci_storage_from_selected()
    assert len(service.project.storages) == 1

    service.undo()

    assert service.project.storages == []
