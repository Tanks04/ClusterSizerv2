"""Real Qt test for the Attention Needed panel's wiring into
SummaryPage - populated on refresh() and kept live as the project
changes."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.pages.summary_page import SummaryPage
from src.models.maintenance_item import MaintenanceItem
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_empty_project_shows_all_clear():
    service = ProjectService()
    page = SummaryPage(service)

    assert len(page.attention_panel._item_labels) == 1
    assert "No issues found" in page.attention_panel._item_labels[0].text()


def test_panel_updates_live_when_project_changes():
    service = ProjectService()
    page = SummaryPage(service)
    assert "No issues found" in page.attention_panel._item_labels[0].text()

    expired_item = MaintenanceItem(
        uid="x", name="Test License", category="License", cost=100,
        duration_months=12, expiry_date="2020-01-01",
    )
    service.add_maintenance_item(expired_item)  # fires service.changed -> page.refresh()

    assert any("Test License" in l.text() for l in page.attention_panel._item_labels)


def test_page_content_is_wrapped_in_a_scrollable_area():
    """A long Attention Needed list (or just enough project data) can
    grow the page taller than the window - without a scroll area, that
    content past the bottom would simply be unreachable."""
    from PySide6.QtWidgets import QScrollArea

    service = ProjectService()
    page = SummaryPage(service)

    scroll_area = page.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True


def test_many_attention_items_do_not_crash_the_page():
    service = ProjectService()
    page = SummaryPage(service)

    for i in range(20):
        item = MaintenanceItem(
            uid=f"x{i}", name=f"License {i}", category="License",
            cost=100, duration_months=12, expiry_date="2020-01-01",
        )
        service.add_maintenance_item(item)

    assert len(page.attention_panel._item_labels) == 20
