"""Real Qt tests for SiteCapacityWidget - PySide6 is now actually
installed in this environment (it wasn't for most of this project's
development, which relied on source-inspection/simulation tests
instead - see git history for the earlier version of this file). Pins
two real bugs found from a screenshot: a RAM utilization bar showing
~32.5% fill for a value labeled "65%".

Root causes, both in set_report():
1. setValue() was called BEFORE setRange() for the CPU bar - QProgressBar
   clamps a value against whatever range is CURRENT at that exact call,
   so the first refresh (range still at the constructor's default) got
   clamped, and a later setRange() didn't retroactively fix it.
2. RAM/Storage bars never got their range updated away from the
   constructor's default of 0-200 - a plain percentage (0-100 is "full")
   rendered at roughly half its true fill.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.widgets.site_capacity_widget import SiteCapacityWidget
from src.calculations.sizing import SiteReport
from src.calculations.thresholds import Status


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _report(cpu_ratio=None, ram_ratio=None, storage_ratio=None):
    return SiteReport(
        site="Primary", server_count=1, physical_cores=10, physical_threads=20,
        physical_ram_gb=100, usable_storage_gb=100,
        vm_count=1, vcpu_demand=1, ram_demand_gb=1, disk_demand_gb=1,
        cpu_ratio=cpu_ratio, ram_ratio=ram_ratio, storage_ratio=storage_ratio,
        cpu_status=Status.OK, ram_status=Status.OK, storage_status=Status.OK,
        n_plus_one_ok=True, n_plus_one_check=None, ht_state="all_on",
    )


def test_ram_bar_fill_matches_its_own_label():
    """The exact reported symptom: 65% labeled, bar looked like ~35%."""
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(ram_ratio=0.65))

    assert widget.ram_bar.minimum() == 0
    assert widget.ram_bar.maximum() == 100
    assert widget.ram_bar.value() == 65
    assert widget.ram_bar.text() == "65%"

    fill_percent = widget.ram_bar.value() / widget.ram_bar.maximum() * 100
    assert fill_percent == 65.0


def test_storage_bar_fill_matches_its_own_label():
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(storage_ratio=0.40))

    assert widget.storage_bar.maximum() == 100
    assert widget.storage_bar.value() == 40
    assert widget.storage_bar.value() / widget.storage_bar.maximum() * 100 == 40.0


def test_cpu_bar_fill_is_correct_on_the_very_first_refresh():
    """The order bug only showed up on the FIRST refresh (range still at
    the constructor default when setValue() was called) - a fresh
    widget's very first set_report() call is exactly that case."""
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(cpu_ratio=3.0))

    assert widget.cpu_bar.minimum() == 0
    assert widget.cpu_bar.maximum() == 400
    assert widget.cpu_bar.value() == 300
    assert widget.cpu_bar.text() == "3.0 : 1"

    fill_percent = widget.cpu_bar.value() / widget.cpu_bar.maximum() * 100
    assert fill_percent == 75.0


def test_cpu_bar_fill_correct_across_repeated_refreshes():
    """The staleness bug's fix (reordering setRange/setValue) must hold
    up across multiple refreshes with changing ratios, not just the
    first one."""
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(cpu_ratio=1.0))
    assert widget.cpu_bar.value() == 100

    widget.set_report(_report(cpu_ratio=3.0))
    assert widget.cpu_bar.value() == 300
    assert widget.cpu_bar.value() / widget.cpu_bar.maximum() * 100 == 75.0

    widget.set_report(_report(cpu_ratio=0.5))
    assert widget.cpu_bar.value() == 50


def test_none_ratio_shows_n_a_and_zero_fill():
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(cpu_ratio=None, ram_ratio=None, storage_ratio=None))

    assert widget.cpu_bar.text() == "n/a"
    assert widget.cpu_bar.value() == 0
    assert widget.ram_bar.text() == "n/a"
    assert widget.ram_bar.value() == 0
    assert widget.storage_bar.text() == "n/a"
    assert widget.storage_bar.value() == 0


def test_ram_ratio_over_100_percent_caps_the_bar_but_shows_true_text():
    """An unhealthy overcommit reading (>100%) should max out the bar
    visually rather than trying to render past it, while the text still
    shows the real number."""
    widget = SiteCapacityWidget("Primary")
    widget.set_report(_report(ram_ratio=1.2))

    assert widget.ram_bar.value() == 100  # capped, not 120
    assert widget.ram_bar.text() == "120%"  # text shows the true reading
