"""Tests for a batch of fixes found from real use: Attention item copy
was silently broken (self.sender() returned None, crashing the
handler), a new Storage defaulted to 100TB/80TB instead of 0, and most
importantly - applying a RAID calculation to a Storage (not a Pool)
never actually saved disk_count/disk_size_tb/raid_level, only the
resulting capacity - so the disk composition was invisible no matter
what, the original reported bug. Also covers the simplified "locked
target" RAID Calculator flow (opened contextually from a Storage or
Pool, no separate target picker needed).
"""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMessageBox

from src.calculations.attention import AttentionItem
from src.calculations.thresholds import Status
from src.models.storage import Storage, StoragePool
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# Attention panel copy - the real self.sender() bug
# ----------------------------------------------------------------------

def test_show_context_menu_no_longer_relies_on_sender():
    import src.gui.widgets.attention_panel as ap_module
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    panel.set_items([AttentionItem(Status.WARNING, "Test message")])
    label = panel._item_labels[0]

    fake_menu = MagicMock()
    captured = []
    fake_menu.addAction.side_effect = lambda text, cb: captured.append((text, cb))

    with patch.object(ap_module, "QMenu", return_value=fake_menu):
        panel._show_context_menu(QPoint(10, 10), "Test message", label)

    fake_menu.exec.assert_called_once()
    assert captured[0][0] == "Copy This Item"


def test_copy_this_item_callback_sets_correct_clipboard_text():
    from PySide6.QtGui import QGuiApplication

    import src.gui.widgets.attention_panel as ap_module
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    panel.set_items([AttentionItem(Status.CRITICAL, "Specific message")])
    label = panel._item_labels[0]

    fake_menu = MagicMock()
    captured = []
    fake_menu.addAction.side_effect = lambda text, cb: captured.append((text, cb))

    with patch.object(ap_module, "QMenu", return_value=fake_menu):
        panel._show_context_menu(QPoint(10, 10), "Specific message", label)
    captured[0][1]()

    assert QGuiApplication.clipboard().text() == "Specific message"


def test_copy_all_items_appears_only_with_multiple_items():
    import src.gui.widgets.attention_panel as ap_module
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    panel.set_items([
        AttentionItem(Status.CRITICAL, "Item one"),
        AttentionItem(Status.WARNING, "Item two"),
    ])
    label = panel._item_labels[0]

    fake_menu = MagicMock()
    captured = []
    fake_menu.addAction.side_effect = lambda text, cb: captured.append((text, cb))

    with patch.object(ap_module, "QMenu", return_value=fake_menu):
        panel._show_context_menu(QPoint(10, 10), "Item one", label)

    assert [t for t, _ in captured] == ["Copy This Item", "Copy All Items"]


def test_copy_all_items_callback_joins_with_newlines():
    from PySide6.QtGui import QGuiApplication

    import src.gui.widgets.attention_panel as ap_module
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    panel.set_items([
        AttentionItem(Status.CRITICAL, "Item one"),
        AttentionItem(Status.WARNING, "Item two"),
    ])
    label = panel._item_labels[0]

    fake_menu = MagicMock()
    captured = []
    fake_menu.addAction.side_effect = lambda text, cb: captured.append((text, cb))

    with patch.object(ap_module, "QMenu", return_value=fake_menu):
        panel._show_context_menu(QPoint(10, 10), "Item one", label)
    captured[1][1]()

    assert QGuiApplication.clipboard().text() == "Item one\nItem two"


# ----------------------------------------------------------------------
# Storage dialog defaults - 0/0 instead of 100/80
# ----------------------------------------------------------------------

def test_new_storage_defaults_raw_and_usable_to_zero():
    from src.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog(servers=[])

    assert dialog.raw_spin.value() == 0.0
    assert dialog.usable_spin.value() == 0.0


def test_hci_toggle_does_not_need_to_reset_usable_anymore():
    from src.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog(servers=[])
    dialog.usable_spin.setValue(45.0)

    dialog.is_hci_check.setChecked(True)

    assert dialog.usable_spin.value() == 45.0  # manual entry never touched


# ----------------------------------------------------------------------
# The core bug: applying a RAID calc to a Storage never saved disk data
# ----------------------------------------------------------------------

def test_apply_to_storage_now_saves_disk_composition():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.raw_capacity_tb = 0.0
    storage.usable_capacity_tb = 0.0
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage"))
    dialog.disk_count_spin.setValue(10)
    dialog.disk_size_spin.setValue(12.0)
    dialog.raid_level_combo.setCurrentText("RAID 5")

    with patch.object(QMessageBox, "information"):
        dialog._apply_to_storage(0)

    result = service.project.storages[0]
    assert result.disk_count == 10
    assert result.disk_size_tb == 12.0
    assert result.raid_level == "RAID 5"


def test_selecting_an_existing_storage_auto_preloads_its_disk_data():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.disk_count = 10
    storage.disk_size_tb = 12.0
    storage.raid_level = "RAID 5"
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage"))

    assert dialog.disk_count_spin.value() == 10
    assert dialog.disk_size_spin.value() == 12.0
    assert dialog.raid_level_combo.currentText() == "RAID 5"


def test_storage_pool_auto_preload_still_works_after_refactor():
    """Regression guard - generalizing the preload mechanism to cover
    both Storage and Storage Pool must not break the pool case."""
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="Pool1", disk_count=7, disk_size_tb=15.0, raid_level="RAID 6")
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    assert dialog.disk_count_spin.value() == 7
    assert dialog.disk_size_spin.value() == 15.0
    assert dialog.raid_level_combo.currentText() == "RAID 6"


# ----------------------------------------------------------------------
# Visible disk summary label in StorageDialog
# ----------------------------------------------------------------------

def test_new_storage_shows_not_yet_configured():
    from src.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog(servers=[])

    assert "Not yet configured" in dialog.disk_summary_label.text()


def test_existing_storage_shows_its_disk_composition():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.disk_count = 10
    storage.disk_size_tb = 12.0
    storage.raid_level = "RAID 5"

    dialog = StorageDialog(storage, servers=[])

    assert dialog.disk_summary_label.text() == "10x 12TB, RAID 5"


def test_disk_summary_label_refreshes_after_expanding_via_calculator():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.disk_count = 10
    storage.disk_size_tb = 12.0
    storage.raid_level = "RAID 5"
    service.add_storage(storage)
    dialog = StorageDialog(storage, servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(14)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self._apply()
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        dialog._open_raid_calculator()

    assert dialog.disk_summary_label.text() == "14x 12TB SATA HDD, RAID 5"


# ----------------------------------------------------------------------
# Locked target - no separate picker needed when opened contextually
# ----------------------------------------------------------------------

def test_storage_dialog_locks_target_to_itself():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)
    dialog = StorageDialog(storage, servers=[], service=service)

    with patch("src.gui.dialogs.raid_calculator_dialog.RaidCalculatorDialog") as MockDialog:
        MockDialog.return_value.exec.return_value = 0
        dialog._open_raid_calculator()

    assert MockDialog.call_args.kwargs["locked_target"] == ("Storage", 0)


def test_new_unsaved_storage_forces_calculation_only_mode():
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    dialog = StorageDialog(servers=[], service=service)

    with patch("src.gui.dialogs.raid_calculator_dialog.RaidCalculatorDialog") as MockDialog:
        MockDialog.return_value.exec.return_value = 0
        MockDialog.return_value._current_result = None
        dialog._open_raid_calculator()

    assert MockDialog.call_args.kwargs["locked_target"] == ("None", None)


def test_pool_dialog_locks_target_to_itself():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="Pool1")
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = StoragePoolDialog(pool, service=service)

    with patch("src.gui.dialogs.raid_calculator_dialog.RaidCalculatorDialog") as MockDialog:
        MockDialog.return_value.exec.return_value = 0
        dialog._open_raid_calculator()

    assert MockDialog.call_args.kwargs["locked_target"] == ("Storage Pool", (0, 0))


def test_locked_target_shows_label_and_hides_pickers():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.name = "SAN01"
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service, locked_target=("Storage", 0))
    dialog.show()
    QApplication.processEvents()

    assert dialog.locked_target_label.text() == "SAN01"
    assert dialog.locked_target_label.isVisible() is True
    target_form = dialog.target_type_combo.parentWidget().layout()
    assert target_form.isRowVisible(dialog.target_type_combo) is False


def test_locked_target_pool_label_format():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.name = "SAN01"
    pool = StoragePool(uid="p1", name="NVMe-Pool")
    storage.pools = [pool]
    service.add_storage(storage)

    dialog = RaidCalculatorDialog(service, locked_target=("Storage Pool", (0, 0)))

    assert dialog.locked_target_label.text() == "SAN01 \u203a NVMe-Pool"


def test_locked_target_apply_works_without_touching_any_combo():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.raw_capacity_tb = 0.0
    storage.usable_capacity_tb = 0.0
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service, locked_target=("Storage", 0))
    dialog.disk_count_spin.setValue(10)
    dialog.disk_size_spin.setValue(12.0)

    with patch.object(QMessageBox, "information"):
        dialog._apply()

    assert service.project.storages[0].raw_capacity_tb == 120.0


def test_no_locked_target_behaves_as_before():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    dialog = RaidCalculatorDialog(service)

    assert dialog.locked_target_label.isVisible() is False
