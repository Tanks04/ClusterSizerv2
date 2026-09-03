"""Real Qt tests for RaidCalculatorDialog's widgets - specifically
disk_size_spin, reported directly as broken: typing "1.09" or "1.9"
(common real-world disk sizes) got silently mangled into "19" because
the field was a QSpinBox (integers only) instead of a QDoubleSpinBox.
"""

import pytest
from unittest.mock import MagicMock

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDoubleSpinBox

from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _dialog():
    service = MagicMock()
    service.project.servers = []
    service.project.storages = []
    return RaidCalculatorDialog(service)


def test_disk_size_spin_is_a_double_spin_box():
    dialog = _dialog()

    assert isinstance(dialog.disk_size_spin, QDoubleSpinBox)


def test_disk_size_accepts_1_09():
    dialog = _dialog()

    dialog.disk_size_spin.setValue(1.09)

    assert dialog.disk_size_spin.value() == 1.09


def test_disk_size_accepts_1_9():
    dialog = _dialog()

    dialog.disk_size_spin.setValue(1.9)

    assert dialog.disk_size_spin.value() == 1.9


def test_disk_size_accepts_1_2():
    dialog = _dialog()

    dialog.disk_size_spin.setValue(1.2)

    assert dialog.disk_size_spin.value() == 1.2


def test_calculation_uses_the_full_decimal_disk_size():
    dialog = _dialog()
    dialog.disk_size_spin.setValue(1.09)
    dialog.disk_count_spin.setValue(8)
    dialog.raid_level_combo.setCurrentText("RAID 5")

    dialog._recompute()

    assert dialog._current_result is not None
    assert abs(dialog._current_result.raw_capacity - 8.72) < 0.01
    assert abs(dialog._current_result.usable_capacity - 7.63) < 0.01


def test_reset_leaves_disk_size_at_a_sensible_default():
    dialog = _dialog()
    dialog.disk_size_spin.setValue(1.09)

    dialog._reset()

    assert dialog.disk_size_spin.value() == 4.0
