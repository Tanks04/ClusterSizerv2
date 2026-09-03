"""Real Qt test for SummaryPage's Rack Sizing cards showing "Cloud"
instead of numbers when a site is flagged Cloud - the primary
user-visible surface for the deployment model feature. Cards are
dynamic (one pair per site, keyed by site name in page.rack_cards),
not fixed Primary/DR widgets."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.pages.summary_page import SummaryPage
from src.models.server import Server
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_hybrid_deployment_shows_numbers_for_primary_and_cloud_for_dr():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 2
    server.power_watts = 500.0
    service.add_server(server)
    service.set_deployment_model("DR", "Cloud")

    page = SummaryPage(service)
    page.refresh()

    primary_units, primary_power = page.rack_cards["Primary"]
    dr_units, dr_power = page.rack_cards["DR"]

    assert primary_units.value_label.text() == "2 U"
    assert primary_power.value_label.text() == "500 W"
    assert dr_units.value_label.text() == "Cloud"
    assert dr_power.value_label.text() == "Cloud"


def test_both_sites_on_premise_shows_numbers_on_both():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 1
    service.add_server(server)

    page = SummaryPage(service)
    page.refresh()

    primary_units, _ = page.rack_cards["Primary"]
    dr_units, _ = page.rack_cards["DR"]

    assert primary_units.value_label.text() == "1 U"
    assert dr_units.value_label.text() == "-"  # no DR servers, but still a number-style display


def test_rack_units_shown_without_capacity_is_used_only():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 12
    service.add_server(server)

    page = SummaryPage(service)
    page.refresh()

    units, _ = page.rack_cards["Primary"]
    assert units.value_label.text() == "12 U"


def test_rack_units_shown_within_capacity():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 12
    service.add_server(server)
    service.set_rack_capacity_u("Primary", 84)

    page = SummaryPage(service)
    page.refresh()

    units, _ = page.rack_cards["Primary"]
    assert units.value_label.text() == "12 / 84 U"


def test_rack_units_shown_over_capacity_has_warning_marker():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 12
    service.add_server(server)
    service.set_rack_capacity_u("Primary", 10)

    page = SummaryPage(service)
    page.refresh()

    units, _ = page.rack_cards["Primary"]
    text = units.value_label.text()
    assert "12 / 10 U" in text
    assert "\u26a0" in text


def test_rack_cards_are_dynamic_for_a_third_site():
    service = ProjectService()
    service.project.add_site("DR2")
    service.touch()

    page = SummaryPage(service)
    page.refresh()

    assert "DR2" in page.rack_cards
    units, power = page.rack_cards["DR2"]
    assert units.value_label.text() == "-"


def test_rack_toggle_button_has_visible_styling():
    """Reported as not very visible - now light green, matching the
    same pattern already applied to Preview Failover."""
    service = ProjectService()
    page = SummaryPage(service)

    style = page.rack_toggle_button.styleSheet()

    assert "background-color" in style
    assert style.strip() != ""
