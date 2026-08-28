"""Real Qt tests for the AttentionPanel widget and its wiring into
SummaryPage."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.widgets.attention_panel import AttentionPanel
from src.calculations.attention import AttentionItem
from src.calculations.thresholds import Status


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_empty_list_shows_all_clear_message():
    panel = AttentionPanel()
    panel.set_items([])

    assert len(panel._item_labels) == 1
    assert "No issues found" in panel._item_labels[0].text()


def test_items_are_rendered_one_label_each():
    panel = AttentionPanel()
    panel.set_items([
        AttentionItem(Status.CRITICAL, "Something is critical"),
        AttentionItem(Status.WARNING, "Something is a warning"),
    ])

    assert len(panel._item_labels) == 2
    texts = [l.text() for l in panel._item_labels]
    assert any("Something is critical" in t for t in texts)
    assert any("Something is a warning" in t for t in texts)


def test_setting_items_again_replaces_the_previous_list_not_appends():
    panel = AttentionPanel()
    panel.set_items([AttentionItem(Status.WARNING, "First")])
    panel.set_items([AttentionItem(Status.WARNING, "Second")])

    assert len(panel._item_labels) == 1
    assert "Second" in panel._item_labels[0].text()


def test_setting_items_then_clearing_shows_all_clear_again():
    panel = AttentionPanel()
    panel.set_items([AttentionItem(Status.CRITICAL, "Problem")])
    panel.set_items([])

    assert len(panel._item_labels) == 1
    assert "No issues found" in panel._item_labels[0].text()
