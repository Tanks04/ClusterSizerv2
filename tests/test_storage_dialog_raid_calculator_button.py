"""Tests for StorageDialog's "Open RAID Calculator..." button - replaces
the old inline disk-count/RAID-level calculator entirely, launching the
much more capable standalone RaidCalculatorDialog instead. Also covers
the new StoragePool model (multiple carved-out slices of one array's
disks, each optionally zoned to specific servers).
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.storage_dialog import StorageDialog
from src.models.storage import Storage, StoragePool
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# StorageDialog - old calculator gone, new button in its place
# ----------------------------------------------------------------------

def test_old_inline_calculator_widgets_are_gone():
    dialog = StorageDialog(servers=[])

    assert not hasattr(dialog, "disk_count_spin")
    assert not hasattr(dialog, "disk_size_spin")
    assert not hasattr(dialog, "raid_level_combo")
    assert not hasattr(dialog, "disk_calc_button")


def test_raid_calc_button_exists():
    dialog = StorageDialog(servers=[])

    assert hasattr(dialog, "raid_calc_button")
    assert dialog.raid_calc_button.text() == "Open RAID Calculator..."


def test_opening_without_a_service_shows_a_helpful_message():
    dialog = StorageDialog(servers=[])

    with patch.object(QMessageBox, "information") as mock_info:
        dialog._open_raid_calculator()

    assert mock_info.called


def test_opening_with_a_service_launches_the_real_dialog():
    service = ProjectService()
    dialog = StorageDialog(servers=[], service=service)

    with patch("src.gui.dialogs.raid_calculator_dialog.RaidCalculatorDialog") as MockDialog:
        MockDialog.return_value.exec.return_value = 0
        dialog._open_raid_calculator()

    MockDialog.assert_called_once_with(service, parent=dialog)


# ----------------------------------------------------------------------
# Legacy calculator fields (disk_count/disk_size_tb/raid_level) and
# pools are preserved through an edit, even though no widget edits
# them anymore - the same bug class caught earlier with cluster_name.
# ----------------------------------------------------------------------

def test_new_storage_has_no_legacy_calculator_values():
    dialog = StorageDialog(servers=[])

    storage = dialog.get_storage()

    assert storage.disk_count == 0
    assert storage.disk_size_tb == 0.0
    assert storage.raid_level == ""
    assert storage.pools == []


def test_editing_preserves_legacy_calculator_fields():
    existing = Storage.create_default()
    existing.disk_count = 12
    existing.disk_size_tb = 2.0
    existing.raid_level = "RAID 6"

    dialog = StorageDialog(existing, servers=[])
    result = dialog.get_storage()

    assert result.disk_count == 12
    assert result.disk_size_tb == 2.0
    assert result.raid_level == "RAID 6"


def test_editing_preserves_pools():
    existing = Storage.create_default()
    pool = StoragePool(uid="p1", name="SSD-Tier", raw_capacity_tb=20.0, usable_capacity_tb=15.0)
    existing.pools = [pool]

    dialog = StorageDialog(existing, servers=[])
    result = dialog.get_storage()

    assert len(result.pools) == 1
    assert result.pools[0].name == "SSD-Tier"
    assert result.pools[0].raw_capacity_tb == 20.0


# ----------------------------------------------------------------------
# StoragePool model
# ----------------------------------------------------------------------

def test_storage_defaults_to_no_pools():
    storage = Storage.create_default()

    assert storage.pools == []


def test_pool_can_reference_multiple_servers():
    pool = StoragePool(uid="p1", name="SSD-Tier", server_uids=["srv-a", "srv-b"])

    assert pool.server_uids == ["srv-a", "srv-b"]


def test_pool_clsz_round_trip(tmp_path):
    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.persistence import project_repository

    project = ClusterProject(name="Pool round trip")
    storage = Storage.create_default()
    storage.name = "san01"
    pool1 = StoragePool(uid="p1", name="SSD-Tier", raw_capacity_tb=20.0, usable_capacity_tb=15.0, server_uids=["srv-a"])
    pool2 = StoragePool(uid="p2", name="SATA-Tier", raw_capacity_tb=40.0, usable_capacity_tb=32.0)
    storage.pools = [pool1, pool2]
    project.storages.append(storage)

    path = tmp_path / "p.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert len(loaded.project.storages[0].pools) == 2
    assert loaded.project.storages[0].pools[0].name == "SSD-Tier"
    assert loaded.project.storages[0].pools[0].server_uids == ["srv-a"]
    assert loaded.project.storages[0].pools[1].name == "SATA-Tier"


def test_old_clsz_file_without_pools_defaults_gracefully(tmp_path):
    import json

    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.persistence import project_repository

    project = ClusterProject(name="Pre-pools")
    project.storages.append(Storage.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["storages"][0]["pools"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].pools == []


# ----------------------------------------------------------------------
# VirtualMachine.storage_pool_uid
# ----------------------------------------------------------------------

def test_vm_storage_pool_uid_defaults_empty():
    from src.models.virtual_machine import VirtualMachine

    vm = VirtualMachine.create_default()

    assert vm.storage_pool_uid == ""


def test_vm_storage_pool_uid_clsz_round_trip(tmp_path):
    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.models.virtual_machine import VirtualMachine
    from src.persistence import project_repository

    project = ClusterProject(name="VM pool round trip")
    vm = VirtualMachine.create_default()
    vm.storage_uid = "s1"
    vm.storage_pool_uid = "p1"
    project.vms.append(vm)

    path = tmp_path / "vp.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.vms[0].storage_pool_uid == "p1"
