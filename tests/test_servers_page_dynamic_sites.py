"""Real Qt test confirming ServersPage passes the project's actual site
list into ServerDialog - the exact bug reported directly: editing a
server only offered Primary/DR, never a custom site like DR2, even
though Storage's dialog already worked correctly."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.pages.servers_page import ServersPage
from src.models.server import Server
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _spy_sites(monkeypatch):
    captured = {}
    original_init = ServerDialog.__init__

    def spy_init(self, *args, **kwargs):
        captured["sites"] = kwargs.get("sites")
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(ServerDialog, "__init__", spy_init)
    monkeypatch.setattr(ServerDialog, "exec", lambda self: False)
    return captured


def test_add_server_passes_the_project_site_list(monkeypatch):
    service = ProjectService()
    service.project.add_site("DR2")
    page = ServersPage(service)
    captured = _spy_sites(monkeypatch)

    page._add_server()

    assert captured["sites"] == ["Primary", "DR", "DR2"]


def test_edit_server_passes_the_project_site_list(monkeypatch):
    service = ProjectService()
    service.project.add_site("DR2")
    server = Server.create_default()
    service.add_server(server)
    page = ServersPage(service)
    page.table.selectRow(0)
    captured = _spy_sites(monkeypatch)

    page._edit_server()

    assert captured["sites"] == ["Primary", "DR", "DR2"]
