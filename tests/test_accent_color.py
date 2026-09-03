"""Tests for the app-wide selection/accent color setting - reported
directly as "ta plava mi smeta" (Qt's default selection blue isn't to
everyone's taste). Covers persistence, the QPalette-based theming
function, and the Settings page color picker end to end.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    from src.persistence import app_preferences
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "preferences.json")
    yield


# ----------------------------------------------------------------------
# app_preferences
# ----------------------------------------------------------------------

def test_accent_color_defaults_to_the_apps_existing_blue():
    from src.persistence import app_preferences

    assert app_preferences.load_accent_color() == "#1976d2"


def test_accent_color_persists():
    from src.persistence import app_preferences

    app_preferences.set_accent_color("#ff5722")

    assert app_preferences.load_accent_color() == "#ff5722"


def test_missing_preferences_file_defaults_gracefully(tmp_path, monkeypatch):
    from src.persistence import app_preferences
    monkeypatch.setattr(app_preferences, "PREFERENCES_PATH", tmp_path / "does_not_exist.json")

    assert app_preferences.load_accent_color() == "#1976d2"


# ----------------------------------------------------------------------
# theming.apply_accent_color
# ----------------------------------------------------------------------

def test_apply_accent_color_sets_highlight_role(qapp):
    from src.gui.theming import apply_accent_color

    apply_accent_color(qapp, "#e91e63")

    assert qapp.palette().color(QPalette.ColorRole.Highlight).name() == "#e91e63"


def test_apply_accent_color_sets_readable_highlighted_text(qapp):
    from src.gui.theming import apply_accent_color

    apply_accent_color(qapp, "#e91e63")

    assert qapp.palette().color(QPalette.ColorRole.HighlightedText).name() == "#ffffff"


# ----------------------------------------------------------------------
# Settings page picker
# ----------------------------------------------------------------------

def test_settings_page_shows_current_accent_color():
    from unittest.mock import patch

    from src.gui.pages.settings_page import SettingsPage
    from src.services.project_service import ProjectService

    service = ProjectService()
    page = SettingsPage(service)

    assert page.accent_color_button.text() == "#1976d2"


def test_picking_a_color_saves_it():
    from unittest.mock import patch

    from src.gui.pages.settings_page import SettingsPage
    from src.persistence import app_preferences
    from src.services.project_service import ProjectService

    service = ProjectService()
    page = SettingsPage(service)

    with patch("src.gui.pages.settings_page.QColorDialog.getColor", return_value=QColor("#ff5722")):
        page._pick_accent_color()

    assert page.accent_color_button.text() == "#ff5722"
    assert app_preferences.load_accent_color() == "#ff5722"


def test_picking_a_color_applies_it_live(qapp):
    from unittest.mock import patch

    from src.gui.pages.settings_page import SettingsPage
    from src.services.project_service import ProjectService

    service = ProjectService()
    page = SettingsPage(service)

    with patch("src.gui.pages.settings_page.QColorDialog.getColor", return_value=QColor("#009688")):
        page._pick_accent_color()

    assert qapp.palette().color(QPalette.ColorRole.Highlight).name() == "#009688"


def test_cancelling_the_picker_changes_nothing():
    from unittest.mock import patch

    from src.gui.pages.settings_page import SettingsPage
    from src.persistence import app_preferences
    from src.services.project_service import ProjectService

    service = ProjectService()
    page = SettingsPage(service)

    with patch("src.gui.pages.settings_page.QColorDialog.getColor", return_value=QColor()):  # invalid = cancelled
        page._pick_accent_color()

    assert page.accent_color_button.text() == "#1976d2"
    assert app_preferences.load_accent_color() == "#1976d2"


def test_existing_saved_color_loads_into_a_freshly_opened_page():
    from src.gui.pages.settings_page import SettingsPage
    from src.persistence import app_preferences
    from src.services.project_service import ProjectService

    app_preferences.set_accent_color("#8bc34a")
    service = ProjectService()

    page = SettingsPage(service)

    assert page.accent_color_button.text() == "#8bc34a"


# ----------------------------------------------------------------------
# QSS override - the actual fix for the reported bug: QPalette alone
# isn't honored by some native OS styles for item-view selection
# ----------------------------------------------------------------------

def test_apply_accent_color_injects_qss_override(qapp):
    from src.gui.theming import apply_accent_color

    apply_accent_color(qapp, "#4caf50")

    assert "#4caf50" in qapp.styleSheet()
    assert "QTableView::item:selected" in qapp.styleSheet()


def test_changing_color_replaces_the_qss_block_not_duplicates_it(qapp):
    from src.gui.theming import apply_accent_color

    apply_accent_color(qapp, "#4caf50")
    apply_accent_color(qapp, "#f44336")

    assert "#f44336" in qapp.styleSheet()
    assert "#4caf50" not in qapp.styleSheet()
    assert qapp.styleSheet().count("accent color override") == 2  # start+end markers only


def test_apply_accent_color_preserves_the_rest_of_the_stylesheet(qapp):
    from src.gui.theming import apply_accent_color

    qapp.setStyleSheet("QPushButton { color: red; }")

    apply_accent_color(qapp, "#4caf50")

    assert "QPushButton { color: red; }" in qapp.styleSheet()


def test_reapplying_same_color_is_idempotent(qapp):
    from src.gui.theming import apply_accent_color

    apply_accent_color(qapp, "#4caf50")
    apply_accent_color(qapp, "#4caf50")

    assert qapp.styleSheet().count("#4caf50") == 1
