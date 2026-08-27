"""Real Qt test for SummaryPage's Rack Sizing cards showing "Cloud"
instead of numbers when a site is flagged Cloud - the primary
user-visible surface for the deployment model feature."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.gui.pages.summary_page import SummaryPage
from src.models.server import Server


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
    service.set_dr_deployment_model("Cloud")

    page = SummaryPage(service)
    page.refresh()

    assert page.card_primary_rack_units.value_label.text() == "2 U"
    assert page.card_primary_power.value_label.text() == "500 W"
    assert page.card_dr_rack_units.value_label.text() == "Cloud"
    assert page.card_dr_power.value_label.text() == "Cloud"


def test_both_sites_on_premise_shows_numbers_on_both():
    service = ProjectService()
    server = Server.create_default()
    server.site = "Primary"
    server.rack_units = 1
    service.add_server(server)

    page = SummaryPage(service)
    page.refresh()

    assert page.card_primary_rack_units.value_label.text() == "1 U"
    assert page.card_dr_rack_units.value_label.text() == "-"  # no DR servers, but still a number-style display
