"""Real Qt tests for MultiSelectTableView - PySide6 is now actually
installed in this environment (it wasn't for most of this project's
development, which relied on source-inspection tests instead - see git
history for the earlier version of this file). Pins a real bug:
setStretchLastSection was overriding resizeColumnsToContents()'s
computed width for the last column, forcibly squeezing it to viewport
width. That mattered a lot for a free-text last column like Notes/OS -
a long value got ellipsized with no way to see the rest short of
opening the row's edit dialog. Applies to every CRUD table in the app
(Servers/Storage/VMs/Network/Backup/Pricing), since they all share this
one view class.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import QApplication

from src.gui.widgets.multi_select_table import MultiSelectTableView


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeModel(QAbstractTableModel):
    """Minimal two-column model: a short Name column and a Notes column
    that can hold a very long value, matching the real-world Notes/OS
    columns this bug affected."""

    def __init__(self, notes_text: str):
        super().__init__()
        self._notes_text = notes_text

    def rowCount(self, parent=QModelIndex()):
        return 1

    def columnCount(self, parent=QModelIndex()):
        return 2

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return ["Name", "Notes"][section]

    def data(self, index, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return "srv-01" if index.column() == 0 else self._notes_text


def test_horizontal_scrollbar_policy_is_as_needed():
    table = MultiSelectTableView()
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_stretch_last_section_is_disabled():
    table = MultiSelectTableView()
    assert table.horizontalHeader().stretchLastSection() is False


def test_long_notes_column_keeps_its_full_content_width_not_squeezed_to_viewport():
    """The actual bug, demonstrated: a long Notes value must produce a
    column width reflecting its real content, not get force-fit into
    whatever's left of a (here, deliberately narrow) viewport - which is
    exactly what setStretchLastSection(True) used to do."""
    long_notes = "N" * 300  # far wider than any reasonable viewport
    model = _FakeModel(long_notes)

    table = MultiSelectTableView()
    table.resize(200, 100)  # narrow viewport - the old bug would squeeze column 1 to fit this
    table.set_source_model(model)
    table.resizeColumnsToContents()

    notes_column_width = table.columnWidth(1)
    # A column sized for 300 characters must be far wider than the
    # table's own narrow viewport - proving it wasn't clamped down.
    assert notes_column_width > table.viewport().width()
    assert notes_column_width > 500  # generous floor - real content-based sizing, not a fixed/default width


def test_short_content_does_not_force_full_viewport_width():
    """Without stretch-last-section, a narrow value's column stays
    narrow (spreadsheet-like behavior) instead of being artificially
    stretched to fill unused space - not a bug, just confirming the
    deliberate trade-off made in dropping setStretchLastSection."""
    model = _FakeModel("ok")
    table = MultiSelectTableView()
    table.resize(2000, 100)  # deliberately much wider than the content needs
    table.set_source_model(model)
    table.resizeColumnsToContents()

    assert table.columnWidth(1) < 500  # sized for "ok", not stretched to fill 2000px
