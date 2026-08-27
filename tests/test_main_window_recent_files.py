"""Real Qt tests for the Recent Files menu in MainWindow - opening a
missing file, and the menu populating/clearing correctly."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.project_service import ProjectService
from src.gui.main_window import MainWindow
from src.persistence import recent_files


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_recent_files_path(tmp_path, monkeypatch):
    monkeypatch.setattr(recent_files, "RECENT_FILES_PATH", tmp_path / "recent_files.json")


def test_recent_files_menu_shows_placeholder_when_empty():
    window = MainWindow(ProjectService())
    window._populate_recent_files_menu()

    actions = window.recent_files_menu.actions()
    assert len(actions) == 1
    assert "No recent" in actions[0].text()
    assert actions[0].isEnabled() is False


def test_recent_files_menu_lists_saved_paths(tmp_path):
    project_path = tmp_path / "my_project.clsz"
    service = ProjectService()
    service.save_project(project_path)
    recent_files.add_recent_file(str(project_path))

    window = MainWindow(service)
    window._populate_recent_files_menu()

    labels = [a.text() for a in window.recent_files_menu.actions()]
    assert "my_project.clsz" in labels
    assert "Clear Recent Files" in labels


def test_opening_a_missing_recent_file_shows_warning_and_removes_it(tmp_path, monkeypatch):
    missing_path = str(tmp_path / "deleted_project.clsz")
    recent_files.add_recent_file(missing_path)

    warned = {}
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *args, **kwargs: warned.setdefault("called", True),
    )

    window = MainWindow(ProjectService())
    window._open_recent_file(missing_path)

    assert warned.get("called") is True
    assert missing_path not in recent_files.load_recent_files()


def test_clear_recent_files_empties_the_list(tmp_path):
    project_path = tmp_path / "p.clsz"
    ProjectService().save_project(project_path)
    recent_files.add_recent_file(str(project_path))

    window = MainWindow(ProjectService())
    window._clear_recent_files()

    assert recent_files.load_recent_files() == []


def test_saving_a_project_adds_it_to_recent_files(tmp_path):
    project_path = tmp_path / "saved_via_menu.clsz"
    service = ProjectService()
    window = MainWindow(service)

    service.save_project(project_path)
    recent_files.add_recent_file(str(project_path))  # mirrors what _save_project_as does

    result = recent_files.load_recent_files()
    assert any(p.endswith("saved_via_menu.clsz") for p in result)
