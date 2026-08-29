"""Real Qt tests for the Deployment Model and Rack Capacity sections of
SettingsPage - per-site On-Premise/Cloud and rack capacity, applied
immediately (not batched with the threshold Apply button). Rows are
dynamic (keyed by site name in dicts), not fixed Primary/DR widgets."""

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

    assert page.deployment_combos["Primary"].currentText() == "On-Premise"
    assert page.deployment_combos["DR"].currentText() == "On-Premise"


def test_changing_dr_combo_applies_immediately_without_apply_button():
    service = ProjectService()
    page = SettingsPage(service)

    page.deployment_combos["DR"].setCurrentText("Cloud")

    assert service.project.deployment_model_for("DR") == "Cloud"
    assert service.project.deployment_model_for("Primary") == "On-Premise"  # unaffected


def test_change_is_undoable():
    service = ProjectService()
    page = SettingsPage(service)

    page.deployment_combos["Primary"].setCurrentText("Cloud")
    assert service.project.deployment_model_for("Primary") == "Cloud"

    service.undo()
    assert service.project.deployment_model_for("Primary") == "On-Premise"


def test_rack_capacity_defaults_to_zero():
    service = ProjectService()
    page = SettingsPage(service)

    assert page.rack_capacity_spins["Primary"].value() == 0
    assert page.rack_capacity_spins["DR"].value() == 0


def test_changing_rack_capacity_applies_immediately():
    service = ProjectService()
    page = SettingsPage(service)

    page.rack_capacity_spins["Primary"].setValue(84)

    assert service.project.rack_capacity_u_for("Primary") == 84
    assert service.project.rack_capacity_u_for("DR") == 0  # unaffected


def test_rack_capacity_change_is_undoable():
    service = ProjectService()
    page = SettingsPage(service)

    page.rack_capacity_spins["DR"].setValue(24)
    assert service.project.rack_capacity_u_for("DR") == 24

    service.undo()

    assert service.project.rack_capacity_u_for("DR") == 0


def test_adding_a_site_creates_new_deployment_and_rack_rows():
    service = ProjectService()
    page = SettingsPage(service)

    page.new_site_edit.setText("DR2")
    page._add_site()

    assert "DR2" in page.deployment_combos
    assert "DR2" in page.rack_capacity_spins
    assert "DR2" in service.project.site_names


def test_removing_a_site_via_ui_removes_its_rows(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    service = ProjectService()
    service.add_site("DR2")
    page = SettingsPage(service)
    page._rebuild_site_rows()

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    page._remove_site("DR2")

    assert "DR2" not in page.deployment_combos
    assert "DR2" not in service.project.site_names


def test_removing_primary_via_ui_shows_a_warning_and_does_not_remove_it(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    service = ProjectService()
    page = SettingsPage(service)

    warned = {}
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.setdefault("called", True))

    page._remove_site("Primary")

    assert warned.get("called") is True
    assert "Primary" in service.project.site_names


def test_page_content_is_wrapped_in_a_scrollable_area():
    """A project with several sites (each adding a row to Deployment
    Model AND Rack Capacity) can make the page taller than a typical
    window - without a scroll area, word-wrapped note labels can end
    up squeezed into too little vertical space and render cut off/
    overlapping instead of just being clipped past the bottom."""
    from PySide6.QtWidgets import QScrollArea

    service = ProjectService()
    service.add_site("DR2")
    page = SettingsPage(service)

    scroll_area = page.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True



def test_deployment_form_fields_stay_at_size_hint():
    """Widgets should be sized to their content, not stretched to fill
    the window - reported directly from a screenshot showing every
    combo/spinbox spanning the full window width."""
    from PySide6.QtWidgets import QFormLayout

    service = ProjectService()
    page = SettingsPage(service)

    assert page.deployment_form.fieldGrowthPolicy() == QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint
    assert page.rack_capacity_form.fieldGrowthPolicy() == QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint


def test_wheel_scroll_without_focus_does_not_change_deployment_combo():
    """The actual root cause of settings changing "by themselves" while
    scrolling the page: Qt lets a combo/spin box under the cursor
    consume a wheel event and change its value even without focus.
    Reported directly after the user found Deployment Model and
    threshold values had changed just from scrolling past them."""
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QWheelEvent

    service = ProjectService()
    page = SettingsPage(service)
    combo = page.deployment_combos["DR"]
    assert combo.currentText() == "On-Premise"

    wheel_event = QWheelEvent(
        QPoint(5, 5), QPoint(5, 5), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    QApplication.instance().sendEvent(combo, wheel_event)

    assert combo.currentText() == "On-Premise"


def test_wheel_scroll_without_focus_does_not_change_threshold_spinbox():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QWheelEvent

    service = ProjectService()
    page = SettingsPage(service)
    original = page.cpu_warning_spin.value()

    wheel_event = QWheelEvent(
        QPoint(5, 5), QPoint(5, 5), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    QApplication.instance().sendEvent(page.cpu_warning_spin, wheel_event)

    assert page.cpu_warning_spin.value() == original


def test_setting_value_directly_still_works_normally():
    """The wheel-block must not interfere with real interaction (click,
    keyboard, or programmatic set) - only unfocused wheel scroll."""
    service = ProjectService()
    page = SettingsPage(service)

    page.deployment_combos["DR"].setCurrentText("Cloud")

    assert page.deployment_combos["DR"].currentText() == "Cloud"
    assert service.project.deployment_model_for("DR") == "Cloud"
