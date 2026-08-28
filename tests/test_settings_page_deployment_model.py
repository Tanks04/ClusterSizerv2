"""Real Qt tests for the Deployment Model section of SettingsPage -
per-site On-Premise/Cloud, applied immediately (not batched with the
threshold Apply button)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.gui.pages.settings_page import SettingsPage


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_defaults_to_on_premise_for_both_sites():
    service = ProjectService()
    page = SettingsPage(service)

    assert page.primary_deployment_combo.currentText() == "On-Premise"
    assert page.dr_deployment_combo.currentText() == "On-Premise"


def test_changing_dr_combo_applies_immediately_without_apply_button():
    service = ProjectService()
    page = SettingsPage(service)

    page.dr_deployment_combo.setCurrentText("Cloud")

    assert service.project.dr_deployment_model == "Cloud"
    assert service.project.primary_deployment_model == "On-Premise"  # unaffected


def test_change_is_undoable():
    service = ProjectService()
    page = SettingsPage(service)

    page.primary_deployment_combo.setCurrentText("Cloud")
    assert service.project.primary_deployment_model == "Cloud"

    service.undo()
    assert service.project.primary_deployment_model == "On-Premise"


def test_rack_capacity_defaults_to_zero():
    service = ProjectService()
    page = SettingsPage(service)

    assert page.primary_rack_capacity_spin.value() == 0
    assert page.dr_rack_capacity_spin.value() == 0


def test_changing_rack_capacity_applies_immediately():
    service = ProjectService()
    page = SettingsPage(service)

    page.primary_rack_capacity_spin.setValue(84)

    assert service.project.primary_rack_capacity_u == 84
    assert service.project.dr_rack_capacity_u == 0  # unaffected


def test_rack_capacity_change_is_undoable():
    service = ProjectService()
    page = SettingsPage(service)

    page.dr_rack_capacity_spin.setValue(24)
    assert service.project.dr_rack_capacity_u == 24

    service.undo()

    assert service.project.dr_rack_capacity_u == 0
