"""Tests for the Simple/Advanced Mode toggle - Clusters, Storage Pool
assignment, and VLAN assignment are opt-in concepts most projects never
need, so they're hidden by default until explicitly turned on via
View > Advanced Mode. Covers the app_preferences persistence, each
page's set_advanced_mode, both dialogs' advanced-only rows, and the
full toggle-through-MainWindow interaction with lazy tab construction.
"""

import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.models.cluster import Cluster
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    """Every test gets its own preferences.json so tests can't leak
    advanced-mode state into each other or the real ~/.clustersizer."""
    from src.persistence import app_preferences
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "preferences.json")
    yield


# ----------------------------------------------------------------------
# app_preferences
# ----------------------------------------------------------------------

def test_advanced_mode_defaults_false():
    from src.persistence import app_preferences

    assert app_preferences.load_advanced_mode() is False


def test_advanced_mode_persists():
    from src.persistence import app_preferences

    app_preferences.set_advanced_mode(True)

    assert app_preferences.load_advanced_mode() is True


def test_advanced_mode_can_be_turned_back_off():
    from src.persistence import app_preferences

    app_preferences.set_advanced_mode(True)
    app_preferences.set_advanced_mode(False)

    assert app_preferences.load_advanced_mode() is False


def test_missing_preferences_file_defaults_gracefully(tmp_path, monkeypatch):
    from src.persistence import app_preferences
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "does_not_exist.json")

    assert app_preferences.load_advanced_mode() is False


# ----------------------------------------------------------------------
# ServersPage
# ----------------------------------------------------------------------

def test_servers_page_hides_cluster_section_by_default():
    from src.gui.pages.servers_page import ServersPage

    service = ProjectService()
    page = ServersPage(service)
    page.show()
    QApplication.processEvents()

    assert page.cluster_section.isVisible() is False
    assert page.table.isColumnHidden(17) is True


def test_servers_page_shows_cluster_section_when_enabled():
    from src.gui.pages.servers_page import ServersPage

    service = ProjectService()
    page = ServersPage(service)
    page.show()
    QApplication.processEvents()

    page.set_advanced_mode(True)
    QApplication.processEvents()

    assert page.cluster_section.isVisible() is True
    assert page.table.isColumnHidden(17) is False


def test_servers_page_picks_up_saved_preference_at_construction():
    from src.persistence import app_preferences
    from src.gui.pages.servers_page import ServersPage

    app_preferences.set_advanced_mode(True)
    service = ProjectService()
    page = ServersPage(service)

    assert page.table.isColumnHidden(17) is False


# ----------------------------------------------------------------------
# ServerDialog
# ----------------------------------------------------------------------

def test_server_dialog_hides_cluster_row_by_default():
    from src.gui.dialogs.server_dialog import ServerDialog

    dialog = ServerDialog()

    assert dialog.form_layout.isRowVisible(dialog.cluster_combo) is False


def test_server_dialog_shows_cluster_row_when_advanced_enabled():
    from src.persistence import app_preferences
    from src.gui.dialogs.server_dialog import ServerDialog

    app_preferences.set_advanced_mode(True)
    dialog = ServerDialog()

    assert dialog.form_layout.isRowVisible(dialog.cluster_combo) is True


# ----------------------------------------------------------------------
# VMDialog
# ----------------------------------------------------------------------

def test_vm_dialog_hides_advanced_rows_by_default():
    from src.gui.dialogs.vm_dialog import VMDialog

    dialog = VMDialog()

    assert dialog.form_layout.isRowVisible(dialog.vlan_combo) is False
    assert dialog.form_layout.isRowVisible(dialog.storage_combo) is False
    assert dialog.form_layout.isRowVisible(dialog.cluster_combo) is False


def test_vm_dialog_shows_advanced_rows_when_enabled():
    from src.persistence import app_preferences
    from src.gui.dialogs.vm_dialog import VMDialog

    app_preferences.set_advanced_mode(True)
    dialog = VMDialog()

    assert dialog.form_layout.isRowVisible(dialog.vlan_combo) is True
    assert dialog.form_layout.isRowVisible(dialog.storage_combo) is True
    assert dialog.form_layout.isRowVisible(dialog.cluster_combo) is True


# ----------------------------------------------------------------------
# VirtualMachinesPage
# ----------------------------------------------------------------------

def test_vms_page_hides_cluster_widgets_and_columns_by_default():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    assert page.cluster_move_widgets.isVisible() is False
    assert page.table.isColumnHidden(11) is True  # VLAN
    assert page.table.isColumnHidden(12) is True  # Cluster


def test_vms_page_shows_cluster_widgets_when_enabled():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = VirtualMachinesPage(service)
    page.show()
    QApplication.processEvents()

    page.set_advanced_mode(True)
    QApplication.processEvents()

    assert page.cluster_move_widgets.isVisible() is True
    assert page.table.isColumnHidden(11) is False
    assert page.table.isColumnHidden(12) is False


def test_vms_page_add_to_cluster_action_hidden_by_default():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = VirtualMachinesPage(service)

    labels = [label for label, _ in page.table._custom_actions]

    assert not any("Add to Cluster" in l for l in labels)


def test_vms_page_add_to_cluster_action_shown_when_enabled():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    page = VirtualMachinesPage(service)
    page.set_advanced_mode(True)

    labels = [label for label, _ in page.table._custom_actions]

    assert any("Add to Cluster" in l for l in labels)


def test_vms_page_toggling_off_hides_again():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    page = VirtualMachinesPage(service)
    page.set_advanced_mode(True)
    page.set_advanced_mode(False)

    assert page.cluster_move_widgets.isVisible() is False
    assert page.table.isColumnHidden(12) is True


# ----------------------------------------------------------------------
# NetworkPage
# ----------------------------------------------------------------------

def test_network_page_hides_vlans_section_by_default():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    page = NetworkPage(service)
    page.show()
    QApplication.processEvents()

    assert page.vlans_section.isVisible() is False


def test_network_page_shows_vlans_section_when_enabled():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    page = NetworkPage(service)
    page.show()
    QApplication.processEvents()

    page.set_advanced_mode(True)
    QApplication.processEvents()

    assert page.vlans_section.isVisible() is True


# ----------------------------------------------------------------------
# MainWindow - View menu, live updates, and lazy tab construction
# ----------------------------------------------------------------------

def test_view_menu_advanced_mode_action_exists_and_starts_unchecked():
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)

    assert window.advanced_mode_action.isCheckable() is True
    assert window.advanced_mode_action.isChecked() is False


def test_toggling_saves_the_preference():
    from src.gui.main_window import MainWindow
    from src.persistence import app_preferences

    service = ProjectService()
    window = MainWindow(service)

    window.advanced_mode_action.setChecked(True)

    assert app_preferences.load_advanced_mode() is True


def test_toggling_updates_an_already_built_page_live():
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)
    window._on_tab_changed(1)  # Servers tab
    servers_page = window._tab_containers[1].page
    assert servers_page.table.isColumnHidden(17) is True

    window.advanced_mode_action.setChecked(True)

    assert servers_page.table.isColumnHidden(17) is False


def test_a_page_built_after_toggling_picks_up_the_preference_automatically():
    """The key lazy-construction interaction: a tab not yet visited
    when the toggle changes must still come up correctly configured
    the first time it IS visited, with no direct call needed."""
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)
    window.advanced_mode_action.setChecked(True)

    window._on_tab_changed(4)  # VMs tab - never built before this
    vms_page = window._tab_containers[4].page

    assert vms_page is not None
    assert vms_page._advanced_mode is True
    assert vms_page.table.isColumnHidden(12) is False


def test_toggling_off_hides_an_already_built_page_again():
    from src.gui.main_window import MainWindow

    service = ProjectService()
    window = MainWindow(service)
    window._on_tab_changed(1)
    servers_page = window._tab_containers[1].page
    window.advanced_mode_action.setChecked(True)
    assert servers_page.table.isColumnHidden(17) is False

    window.advanced_mode_action.setChecked(False)

    assert servers_page.table.isColumnHidden(17) is True


def test_toggle_does_not_lose_or_unassign_existing_cluster_data():
    """Toggling only hides UI - it must never clear cluster_uid or
    delete Cluster entities."""
    from src.gui.main_window import MainWindow

    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)
    window = MainWindow(service)

    window.advanced_mode_action.setChecked(True)
    window.advanced_mode_action.setChecked(False)

    assert len(service.project.clusters) == 1
    assert service.project.servers[0].cluster_uid == cluster.uid
