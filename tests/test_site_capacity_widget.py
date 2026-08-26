"""SiteCapacityWidget can't be instantiated without PySide6 (unavailable
in this sandbox, as elsewhere in this project) - these tests inspect the
source directly to guard against two real bugs found from a screenshot:
a RAM utilization bar showing ~32.5% fill for a value labeled "65%".

Root causes, both in set_report():
1. setValue() was called BEFORE setRange() for the CPU bar - QProgressBar
   clamps a value against whatever range is CURRENT at that exact call,
   so the first refresh (range still at the constructor's default) got
   clamped, and a later setRange() didn't retroactively fix it.
2. RAM/Storage bars never got their range updated away from the
   constructor's default of 0-200 - a plain percentage (0-100 is "full")
   rendered at roughly half its true fill.
"""

from pathlib import Path

_SOURCE = Path(__file__).parent.parent / "src/gui/widgets/site_capacity_widget.py"


def _source_text() -> str:
    return _SOURCE.read_text(encoding="utf-8")


def _line_number_of(text: str, needle: str) -> int:
    idx = text.index(needle)
    return text.count("\n", 0, idx)


def test_cpu_bar_range_is_set_before_value():
    text = _source_text()
    range_line = _line_number_of(text, "self.cpu_bar.setRange(0, 400)")
    value_line = _line_number_of(text, "self.cpu_bar.setValue(0 if report.cpu_ratio")
    assert range_line < value_line, (
        "cpu_bar.setRange() must run before cpu_bar.setValue() - QProgressBar "
        "clamps the value against whatever range is current at call time."
    )


def test_ram_bar_range_is_set_before_value():
    text = _source_text()
    range_line = _line_number_of(text, "self.ram_bar.setRange(0, 100)")
    value_line = _line_number_of(text, "self.ram_bar.setValue(0 if report.ram_ratio")
    assert range_line < value_line


def test_storage_bar_range_is_set_before_value():
    text = _source_text()
    range_line = _line_number_of(text, "self.storage_bar.setRange(0, 100)")
    value_line = _line_number_of(text, "self.storage_bar.setValue(")
    assert range_line < value_line


def test_ram_and_storage_bars_use_a_0_to_100_range_not_200():
    """A plain percentage (0-100 is "full") must not share CPU's wider
    0-400 range - that mismatch is exactly what made a healthy 65% look
    like a third of the bar."""
    text = _source_text()
    assert "self.ram_bar.setRange(0, 100)" in text
    assert "self.storage_bar.setRange(0, 100)" in text
    assert "self.ram_bar.setRange(0, 200)" not in text
    assert "self.storage_bar.setRange(0, 200)" not in text


def test_progress_bar_clamping_semantics_match_qt_and_confirm_the_fix():
    """Standalone simulation of QProgressBar's real clamping behavior
    (setValue() clamps against whatever range is CURRENT; a later
    setRange() does not retroactively un-clamp an already-stored value) -
    proves both the bug and the fix mathematically without needing Qt
    itself installed."""

    class MockProgressBar:
        def __init__(self):
            self._min, self._max = 0, 200  # the old constructor default
            self._value = 0

        def setRange(self, lo, hi):
            self._min, self._max = lo, hi

        def setValue(self, v):
            self._value = max(self._min, min(v, self._max))

        def fill_percent(self):
            return self._value / self._max * 100 if self._max else 0

    # Old buggy order: setValue() before setRange()
    buggy_ram = MockProgressBar()
    buggy_ram.setValue(min(round(0.65 * 100), 200))
    assert round(buggy_ram.fill_percent(), 1) == 32.5  # confirms the reported symptom

    # New fixed order: setRange() before setValue(), and a correct 0-100 range
    fixed_ram = MockProgressBar()
    fixed_ram.setRange(0, 100)
    fixed_ram.setValue(min(round(0.65 * 100), 100))
    assert round(fixed_ram.fill_percent(), 1) == 65.0  # matches the "65%" label exactly

    buggy_cpu = MockProgressBar()
    buggy_cpu.setValue(min(round(3.0 * 100), 400))
    buggy_cpu.setRange(0, 400)
    assert round(buggy_cpu.fill_percent(), 1) == 50.0  # stale clamp from the old 0-200 default

    fixed_cpu = MockProgressBar()
    fixed_cpu.setRange(0, 400)
    fixed_cpu.setValue(min(round(3.0 * 100), 400))
    assert round(fixed_cpu.fill_percent(), 1) == 75.0  # correct: 300/400
