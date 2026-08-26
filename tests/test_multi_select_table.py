"""MultiSelectTableView can't be instantiated without PySide6
(unavailable in this sandbox, as elsewhere in this project) - this test
guards against a real bug via source inspection: setStretchLastSection
was overriding resizeColumnsToContents()'s computed width for the last
column, forcibly squeezing it to viewport width. That mattered a lot
for a free-text last column like Notes/OS - a long value got
ellipsized with no way to see the rest short of opening the row's edit
dialog. Applies to every CRUD table in the app (Servers/Storage/VMs/
Network/Backup/Pricing), since they all share this one view class."""

from pathlib import Path

_SOURCE = Path(__file__).parent.parent / "src/gui/widgets/multi_select_table.py"


def test_stretch_last_section_is_not_called():
    """The word can still appear in a comment/docstring explaining why
    it's avoided - only an actual call like .setStretchLastSection(...)
    would reintroduce the bug."""
    text = _SOURCE.read_text(encoding="utf-8")
    assert "setStretchLastSection(" not in text


def test_horizontal_scrollbar_policy_is_explicit():
    text = _SOURCE.read_text(encoding="utf-8")
    assert "setHorizontalScrollBarPolicy" in text
    assert "ScrollBarAsNeeded" in text
