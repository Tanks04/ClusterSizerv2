"""Real Qt tests for the Cluster Preparation wizard's optional Backup
page - a mini-form that queues one or more Backup Destinations,
committed to the project only after Finish."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
from src.models.cluster_project import DR, PRIMARY, ClusterProject


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_adding_a_destination_without_a_name_shows_a_message(monkeypatch):
    wizard = ClusterPreparationWizard(ClusterProject())

    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))

    wizard.backup_page._add_destination()

    assert informed.get("called") is True
    assert wizard.new_backup_destinations == []


def test_adding_a_valid_destination_queues_it():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.backup_page.initializePage()
    wizard.backup_page.name_edit.setText("veeam-repo-primary")
    wizard.backup_page.site_combo.setCurrentText(PRIMARY)
    wizard.backup_page.type_combo.setCurrentText("NAS")
    wizard.backup_page.raw_capacity_spin.setValue(20.0)

    wizard.backup_page._add_destination()

    assert len(wizard.new_backup_destinations) == 1
    assert wizard.new_backup_destinations[0].name == "veeam-repo-primary"
    assert wizard.new_backup_destinations[0].raw_capacity_tb == 20.0


def test_adding_two_destinations_queues_both():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.backup_page.initializePage()

    wizard.backup_page.name_edit.setText("local")
    wizard.backup_page.site_combo.setCurrentText(PRIMARY)
    wizard.backup_page._add_destination()

    wizard.backup_page.name_edit.setText("offsite")
    wizard.backup_page.site_combo.setCurrentText(DR)
    wizard.backup_page.offsite_check.setChecked(True)
    wizard.backup_page.immutable_check.setChecked(True)
    wizard.backup_page._add_destination()

    assert len(wizard.new_backup_destinations) == 2
    assert wizard.new_backup_destinations[0].name == "local"
    assert wizard.new_backup_destinations[1].name == "offsite"
    assert wizard.new_backup_destinations[1].is_offsite is True
    assert wizard.new_backup_destinations[1].is_immutable is True


def test_form_resets_name_after_add_but_keeps_site():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.backup_page.initializePage()
    wizard.backup_page.name_edit.setText("first")
    wizard.backup_page.site_combo.setCurrentText(DR)

    wizard.backup_page._add_destination()

    assert wizard.backup_page.name_edit.text() == ""
    assert wizard.backup_page.site_combo.currentText() == DR


def test_site_combo_populated_from_project_site_names():
    project = ClusterProject()
    project.add_site("DR2")
    wizard = ClusterPreparationWizard(project)

    wizard.backup_page.initializePage()

    items = [wizard.backup_page.site_combo.itemText(i) for i in range(wizard.backup_page.site_combo.count())]
    assert items == ["Primary", "DR", "DR2"]


def test_location_field_is_optional_and_stored_when_given():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.backup_page.initializePage()
    wizard.backup_page.name_edit.setText("cloud-copy")
    wizard.backup_page.type_combo.setCurrentText("Cloud")
    wizard.backup_page.location_edit.setText("Azure Blob Storage - West Europe")

    wizard.backup_page._add_destination()

    assert wizard.new_backup_destinations[0].location == "Azure Blob Storage - West Europe"
