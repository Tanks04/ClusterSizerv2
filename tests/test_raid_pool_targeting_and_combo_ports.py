"""Tests for a batch of features: RAID Calculator support for a
specific Storage Pool (with auto-preload of existing disk data for
expanding it), a real undo bug found and fixed while building that
(mutating a live object before calling update_storage() meant the undo
snapshot already reflected the new values), and switch "combo ports"
(the same physical multi-speed-capable ports, not separate port banks
per speed).
"""

import copy
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.calculations.networking import format_usage, switch_port_usage
from src.models.network_connection import NetworkConnection
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.storage import Storage, StoragePool
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# StoragePool disk data fields
# ----------------------------------------------------------------------

def test_pool_disk_data_defaults_empty():
    pool = StoragePool(uid="p1", name="Pool")

    assert pool.disk_count == 0
    assert pool.disk_size_tb == 0.0
    assert pool.raid_level == ""


def test_pool_disk_data_clsz_round_trip(tmp_path):
    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.persistence import project_repository

    project = ClusterProject(name="Pool disk data")
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="NVMe-Pool", disk_count=7, disk_size_tb=15.0, raid_level="RAID 5")
    storage.pools = [pool]
    project.storages.append(storage)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    lp = loaded.project.storages[0].pools[0]
    assert lp.disk_count == 7
    assert lp.disk_size_tb == 15.0
    assert lp.raid_level == "RAID 5"


# ----------------------------------------------------------------------
# RAID Calculator - Storage Pool target
# ----------------------------------------------------------------------

def _dialog_with_pool(disk_count=7, disk_size_tb=15.0, raid_level="RAID 5", raw=0.0, usable=0.0):
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.name = "SAN01"
    pool = StoragePool(
        uid="p1", name="NVMe-Pool", disk_count=disk_count, disk_size_tb=disk_size_tb,
        raid_level=raid_level, raw_capacity_tb=raw, usable_capacity_tb=usable,
    )
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)
    return dialog, service


def test_storage_pool_appears_as_a_target_type():
    dialog, _ = _dialog_with_pool()

    items = [dialog.target_type_combo.itemText(i) for i in range(dialog.target_type_combo.count())]

    assert "Storage Pool" in items


def test_selecting_storage_pool_lists_pools_with_array_name():
    dialog, _ = _dialog_with_pool()

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    assert dialog.target_entity_combo.itemText(0) == "SAN01 \u203a NVMe-Pool"


def test_selecting_a_pool_auto_preloads_its_existing_disk_data():
    dialog, _ = _dialog_with_pool(disk_count=7, disk_size_tb=15.0, raid_level="RAID 5")

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    assert dialog.disk_count_spin.value() == 7
    assert dialog.disk_size_spin.value() == 15.0
    assert dialog.raid_level_combo.currentText() == "RAID 5"


def test_pool_with_no_existing_disks_does_not_override_defaults():
    dialog, _ = _dialog_with_pool(disk_count=0)
    dialog.disk_count_spin.setValue(99)

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    assert dialog.disk_count_spin.value() == 99  # untouched, since pool has nothing saved


def test_expanding_a_pool_applies_the_new_disk_count_and_capacity():
    dialog, service = _dialog_with_pool(disk_count=7, disk_size_tb=15.0, raw=105.0, usable=90.0)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))
    dialog.disk_count_spin.setValue(11)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"):
        dialog._apply_to_pool((0, 0))

    pool = service.project.storages[0].pools[0]
    assert pool.disk_count == 11
    assert pool.raw_capacity_tb == 11 * 15.0


def test_applying_to_a_pool_without_existing_capacity_skips_confirmation():
    dialog, service = _dialog_with_pool(disk_count=0, raw=0.0, usable=0.0)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))
    dialog.disk_count_spin.setValue(7)
    dialog.disk_size_spin.setValue(15.0)

    with patch.object(QMessageBox, "question") as mock_q, patch.object(QMessageBox, "information"):
        dialog._apply_to_pool((0, 0))

    assert not mock_q.called


def test_switching_away_from_storage_pool_does_not_raise():
    dialog, _ = _dialog_with_pool()
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("None (just calculating)"))
    # switching back and forth should not raise or duplicate connections
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))

    assert dialog.target_entity_combo.count() == 1


# ----------------------------------------------------------------------
# Undo bug fix - mutating live objects before update_storage/update_server
# ----------------------------------------------------------------------

def test_apply_to_storage_supports_undo():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.raw_capacity_tb = 50.0
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage"))

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"):
        dialog._apply_to_storage(0)
    service.undo()

    assert service.project.storages[0].raw_capacity_tb == 50.0


def test_apply_to_pool_supports_undo():
    dialog, service = _dialog_with_pool(disk_count=7, disk_size_tb=15.0, raw=105.0, usable=90.0)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))
    dialog.disk_count_spin.setValue(11)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"):
        dialog._apply_to_pool((0, 0))
    service.undo()

    assert service.project.storages[0].pools[0].disk_count == 7


def test_apply_to_server_supports_undo():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    server = Server.create_default()
    server.notes = "original note"
    service.add_server(server)
    dialog = RaidCalculatorDialog(service)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Server"))

    with patch.object(QMessageBox, "information"):
        dialog._apply_to_server(0)
    service.undo()

    assert service.project.servers[0].notes == "original note"


# ----------------------------------------------------------------------
# StoragePoolDialog - its own RAID Calculator button
# ----------------------------------------------------------------------

def test_pool_dialog_has_raid_calculator_button():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()

    assert hasattr(dialog, "raid_calc_button")


def test_pool_dialog_without_service_shows_helpful_message():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()

    with patch.object(QMessageBox, "information") as mock_info:
        dialog._open_raid_calculator()

    assert mock_info.called


def test_pool_dialog_preserves_disk_data_through_edit():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    existing = StoragePool(uid="p1", name="Pool", disk_count=7, disk_size_tb=15.0, raid_level="RAID 5")

    dialog = StoragePoolDialog(existing)
    result = dialog.get_pool()

    assert result.disk_count == 7
    assert result.disk_size_tb == 15.0
    assert result.raid_level == "RAID 5"


def test_full_workflow_from_pool_dialog_through_calculator_and_back():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="NVMe-Pool", disk_count=7, disk_size_tb=15.0, raw_capacity_tb=105.0)
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = StoragePoolDialog(pool, service=service)

    def fake_exec(self):
        idx = self.target_type_combo.findText("Storage Pool")
        self.target_type_combo.setCurrentIndex(idx)
        self.disk_count_spin.setValue(11)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self._apply_to_pool((0, 0))
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        dialog._open_raid_calculator()

    assert dialog.raw_spin.value() == 165.0
    assert dialog._loaded_disk_count == 11


# ----------------------------------------------------------------------
# Switch combo ports
# ----------------------------------------------------------------------

def test_switch_defaults_to_non_combo():
    switch = NetworkSwitch.create_default()

    assert switch.is_combo_ports is False


def test_combo_total_ports_uses_max_not_sum():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 1
    switch.ports_10g = 0
    switch.ports_25g = 24
    switch.ports_40g = 0
    switch.ports_100g = 0
    switch.is_combo_ports = True

    assert switch.total_ports == 24


def test_non_combo_total_ports_still_sums():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 1
    switch.ports_25g = 24
    switch.is_combo_ports = False

    assert switch.total_ports == 25


def test_combo_fc_sas_ports_stay_additive():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 0
    switch.ports_25g = 24
    switch.ports_fc = 8
    switch.is_combo_ports = True

    assert switch.total_ports == 24 + 8


def test_combo_port_usage_pools_connections_across_speeds():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 1
    switch.ports_10g = 0
    switch.ports_25g = 24
    switch.ports_40g = 0
    switch.ports_100g = 0
    switch.is_combo_ports = True

    connections = []
    for _ in range(5):
        c = NetworkConnection.create_default()
        c.switch_uid = switch.uid
        c.speed = "25G"
        connections.append(c)
    c = NetworkConnection.create_default()
    c.switch_uid = switch.uid
    c.speed = "1G"
    connections.append(c)

    usage = switch_port_usage(switch, connections)

    assert len(usage) == 1
    assert usage[0].total == 24
    assert usage[0].used == 6


def test_non_combo_port_usage_keeps_speeds_separate():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    switch.ports_25g = 4
    switch.is_combo_ports = False
    c = NetworkConnection.create_default()
    c.switch_uid = switch.uid
    c.speed = "25G"

    usage = switch_port_usage(switch, [c])

    assert len(usage) == 2
    speeds = {u.speed: u for u in usage}
    assert speeds["1G"].total == 48 and speeds["1G"].used == 0
    assert speeds["25G"].total == 4 and speeds["25G"].used == 1


def test_combo_mode_fc_ports_tracked_separately_from_ethernet_pool():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 0
    switch.ports_25g = 24
    switch.ports_fc = 8
    switch.is_combo_ports = True
    c = NetworkConnection.create_default()
    c.switch_uid = switch.uid
    c.speed = "FC"

    usage = switch_port_usage(switch, [c])

    fc_entry = next(u for u in usage if u.speed == "FC")
    assert fc_entry.total == 8
    assert fc_entry.used == 1


def test_combo_overcommit_detected_across_pooled_speeds():
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 0
    switch.ports_25g = 2
    switch.is_combo_ports = True
    connections = []
    for speed in ("25G", "1G", "10G"):
        c = NetworkConnection.create_default()
        c.switch_uid = switch.uid
        c.speed = speed
        connections.append(c)

    usage = switch_port_usage(switch, connections)

    assert usage[0].over_committed is True


def test_switch_dialog_checkbox_round_trip():
    from src.gui.dialogs.switch_dialog import SwitchDialog

    switch = NetworkSwitch.create_default()
    switch.is_combo_ports = True

    dialog = SwitchDialog(switch)
    assert dialog.combo_ports_check.isChecked() is True
    result = dialog.get_switch()
    assert result.is_combo_ports is True


def test_switch_table_shows_combo_marker():
    from PySide6.QtCore import Qt

    from src.gui.models.switch_table_model import SwitchTableModel

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 1
    switch.ports_10g = 0
    switch.ports_25g = 24
    switch.ports_40g = 0
    switch.ports_100g = 0
    switch.is_combo_ports = True
    model = SwitchTableModel([switch], connections_provider=lambda: [])

    text = model.data(model.index(0, 6), Qt.ItemDataRole.DisplayRole)

    assert "combo" in text
    assert "24" in text
    assert "48" not in text  # never sums to a misleading total


def test_switch_table_non_combo_unchanged():
    from PySide6.QtCore import Qt

    from src.gui.models.switch_table_model import SwitchTableModel

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    switch.ports_25g = 4
    switch.is_combo_ports = False
    model = SwitchTableModel([switch], connections_provider=lambda: [])

    text = model.data(model.index(0, 6), Qt.ItemDataRole.DisplayRole)

    assert text == "1G:48 25G:4"
