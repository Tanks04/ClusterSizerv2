"""Tests for a batch of fixes: the same "new entity + RAID calculator"
bug already fixed for StoragePoolDialog also existed for StorageDialog
itself (a brand new Storage had nowhere valid to target, so the
"Which one" picker only offered existing storages); a new disk_type
field (editable, not just a fixed list) tracked alongside disk_count/
disk_size/raid_level; and NetworkConnection.enabled for disabling one
specific link/cable without disabling the whole switch.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.network_connection import NetworkConnection
from src.models.network_switch import NetworkSwitch
from src.models.storage import Storage, StoragePool
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# The critical bug: new Storage + RAID Calculator had nowhere to target
# ----------------------------------------------------------------------

def test_new_storage_calculator_locks_to_none_mode():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    service.add_storage(storage)

    dialog = RaidCalculatorDialog(service, locked_target=("None", None))

    assert dialog.target_type_combo.currentText() == "None (just calculating)"
    assert "New pool" in dialog.locked_target_label.text() or dialog.locked_target_label.isVisible() is False


def test_new_storage_gets_its_own_values_not_an_existing_ones():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    existing = Storage.create_default()
    existing.name = "SAN01"
    existing.disk_count = 5
    existing.disk_size_tb = 4.0
    existing.raw_capacity_tb = 20.0
    service.add_storage(existing)
    new_dialog = StorageDialog(servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(10)
        self.disk_size_spin.setValue(12.0)
        self.raid_level_combo.setCurrentText("RAID 6")
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        new_dialog._open_raid_calculator()

    result = new_dialog.get_storage()
    assert result.disk_count == 10
    assert result.raw_capacity_tb == 120.0


def test_existing_storage_is_never_touched_by_a_new_storages_calculation():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    existing = Storage.create_default()
    existing.disk_count = 5
    existing.raw_capacity_tb = 20.0
    service.add_storage(existing)
    new_dialog = StorageDialog(servers=[], service=service)

    def fake_exec(self):
        self.disk_count_spin.setValue(10)
        self.disk_size_spin.setValue(12.0)
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        new_dialog._open_raid_calculator()

    untouched = service.project.storages[0]
    assert untouched.disk_count == 5
    assert untouched.raw_capacity_tb == 20.0


def test_existing_storage_still_uses_the_locked_target_flow():
    """Regression guard - fixing the new-storage case must not break
    the already-working existing-storage expand workflow."""
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
    from src.gui.dialogs.storage_dialog import StorageDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.disk_count = 7
    storage.disk_size_tb = 15.0
    storage.raw_capacity_tb = 105.0
    service.add_storage(storage)
    dialog = StorageDialog(storage, servers=[], service=service)

    def fake_exec(self):
        assert self.target_type_combo.currentText() == "Storage"
        self.disk_count_spin.setValue(11)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self._apply_to_storage(0)
        return 1

    with patch.object(RaidCalculatorDialog, "exec", fake_exec):
        dialog._open_raid_calculator()

    assert service.project.storages[0].disk_count == 11


# ----------------------------------------------------------------------
# Disk type - editable combo, saved/preloaded like the other fields
# ----------------------------------------------------------------------

def test_disk_type_combo_is_editable():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    dialog = RaidCalculatorDialog(service)

    assert dialog.disk_type_combo.isEditable() is True


def test_custom_disk_type_saves_to_storage():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.raw_capacity_tb = 0.0
    storage.usable_capacity_tb = 0.0
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage"))
    dialog.disk_type_combo.setCurrentText("SCSI UW")

    with patch.object(QMessageBox, "information"):
        dialog._apply_to_storage(0)

    assert service.project.storages[0].disk_type == "SCSI UW"


def test_custom_disk_type_saves_to_pool():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="Pool1")
    storage.pools = [pool]
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)
    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage Pool"))
    dialog.disk_type_combo.setCurrentText("SCSI UW")

    with patch.object(QMessageBox, "information"):
        dialog._apply_to_pool((0, 0))

    assert service.project.storages[0].pools[0].disk_type == "SCSI UW"


def test_disk_type_auto_preloads_for_existing_storage():
    from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog

    service = ProjectService()
    storage = Storage.create_default()
    storage.disk_count = 10
    storage.disk_type = "NVMe Flash"
    service.add_storage(storage)
    dialog = RaidCalculatorDialog(service)

    dialog.target_type_combo.setCurrentIndex(dialog.target_type_combo.findText("Storage"))

    assert dialog.disk_type_combo.currentText() == "NVMe Flash"


def test_storage_dialog_shows_disk_type_in_summary_label():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.disk_count = 10
    storage.disk_size_tb = 12.0
    storage.raid_level = "RAID 5"
    storage.disk_type = "SAS SSD"

    dialog = StorageDialog(storage, servers=[])

    assert dialog.disk_summary_label.text() == "10x 12TB SAS SSD, RAID 5"


def test_pool_dialog_shows_disk_type_in_summary_label():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    pool = StoragePool(uid="p1", name="Pool", disk_count=7, disk_size_tb=15.0,
                        raid_level="RAID 5", disk_type="NVMe Flash")

    dialog = StoragePoolDialog(pool)

    assert dialog.disk_summary_label.text() == "7x 15TB NVMe Flash, RAID 5"


def test_pools_table_disks_column_shows_disk_type():
    from src.gui.dialogs.storage_dialog import StorageDialog

    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Pool", disk_count=7, disk_size_tb=15.0, disk_type="NVMe Flash")]

    dialog = StorageDialog(storage, servers=[])

    assert dialog.pools_table.item(0, 1).text() == "7x 15TB NVMe Flash"


def test_docx_report_shows_disk_type_in_pools_table():
    from src.calculations.docx_report import build_docx_report

    project = ClusterProject()
    storage = Storage.create_default()
    storage.name = "SAN01"
    pool = StoragePool(uid="p1", name="Pool", disk_count=7, disk_size_tb=15.0,
                        raid_level="RAID 5", disk_type="NVMe Flash")
    storage.pools = [pool]
    project.storages.append(storage)

    doc = build_docx_report(project, Thresholds(), app_version="test")

    pool_table = next(t for t in doc.tables if "Storage Array" in [c.text for c in t.rows[0].cells])
    row = [c.text for c in pool_table.rows[1].cells]
    assert row[3] == "7x 15TB NVMe Flash, RAID 5"


def test_disk_type_clsz_round_trip(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Disk type round trip")
    storage = Storage.create_default()
    storage.disk_type = "NVMe Flash"
    pool = StoragePool(uid="p1", name="Pool1", disk_type="SCSI UW")
    storage.pools = [pool]
    project.storages.append(storage)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].disk_type == "NVMe Flash"
    assert loaded.project.storages[0].pools[0].disk_type == "SCSI UW"


# ----------------------------------------------------------------------
# NetworkConnection.enabled - disable a specific link/cable
# ----------------------------------------------------------------------

def test_connection_defaults_to_enabled():
    connection = NetworkConnection.create_default()

    assert connection.enabled is True


def test_disabled_connection_excluded_from_port_usage():
    from src.calculations.networking import switch_port_usage

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    conn.speed = "1G"
    conn.enabled = False

    usage = switch_port_usage(switch, [conn])

    used = next(u.used for u in usage if u.speed == "1G")
    assert used == 0


def test_disabling_one_connection_does_not_affect_the_switchs_other_ports():
    from src.calculations.networking import switch_port_usage

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    conn1 = NetworkConnection.create_default()
    conn1.switch_uid = switch.uid
    conn1.speed = "1G"
    conn1.enabled = False
    conn2 = NetworkConnection.create_default()
    conn2.switch_uid = switch.uid
    conn2.speed = "1G"

    usage = switch_port_usage(switch, [conn1, conn2])

    used = next(u.used for u in usage if u.speed == "1G")
    assert used == 1


def test_combo_mode_also_respects_disabled_connections():
    from src.calculations.networking import switch_port_usage

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 0
    switch.ports_25g = 24
    switch.is_combo_ports = True
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    conn.speed = "25G"
    conn.enabled = False

    usage = switch_port_usage(switch, [conn])

    assert usage[0].used == 0


def test_set_enabled_for_connections_excludes_from_usage():
    service = ProjectService()
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    service.add_switch(switch)
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    conn.speed = "1G"
    service.project.connections.append(conn)

    service.set_enabled_for_connections([conn], False)

    from src.calculations.networking import switch_port_usage
    usage = switch_port_usage(switch, service.project.connections)
    used = next(u.used for u in usage if u.speed == "1G")
    assert used == 0


def test_set_enabled_for_connections_re_enable_restores():
    service = ProjectService()
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    service.add_switch(switch)
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    conn.speed = "1G"
    service.project.connections.append(conn)
    service.set_enabled_for_connections([conn], False)

    service.set_enabled_for_connections([conn], True)

    from src.calculations.networking import switch_port_usage
    usage = switch_port_usage(switch, service.project.connections)
    used = next(u.used for u in usage if u.speed == "1G")
    assert used == 1


def test_set_enabled_for_connections_is_one_undo_step():
    service = ProjectService()
    conn1 = NetworkConnection.create_default()
    conn2 = NetworkConnection.create_default()
    service.project.connections.extend([conn1, conn2])

    service.set_enabled_for_connections([conn1, conn2], False)
    assert all(not c.enabled for c in service.project.connections)

    service.undo()

    assert all(c.enabled for c in service.project.connections)


def test_network_page_has_connection_disable_enable_actions():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    page = NetworkPage(service)

    labels = [l for l, _ in page.connection_table._custom_actions]
    assert any("Disable" in l for l in labels)
    assert any("Enable" in l for l in labels)


def test_network_page_disable_connection_via_right_click():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    switch = NetworkSwitch.create_default()
    service.add_switch(switch)
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    service.project.connections.append(conn)
    page = NetworkPage(service)
    page.connection_table.selectRow(0)

    page._set_enabled_for_selected_connections(False)

    assert service.project.connections[0].enabled is False


def test_network_page_disable_connection_no_selection_shows_message(monkeypatch):
    from src.gui.pages.network_page import NetworkPage

    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    conn = NetworkConnection.create_default()
    service.project.connections.append(conn)
    page = NetworkPage(service)

    page._set_enabled_for_selected_connections(False)

    assert informed.get("called") is True


def test_connection_enabled_clsz_round_trip(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Connection enabled round trip")
    conn = NetworkConnection.create_default()
    conn.enabled = False
    project.connections.append(conn)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.connections[0].enabled is False


def test_old_clsz_file_without_connection_enabled_defaults_true(tmp_path):
    import json

    from src.persistence import project_repository

    project = ClusterProject(name="Pre-enabled connection")
    project.connections.append(NetworkConnection.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["connections"][0]["enabled"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.connections[0].enabled is True
