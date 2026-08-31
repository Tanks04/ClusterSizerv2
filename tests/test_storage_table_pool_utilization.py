"""Real Qt tests for StorageTableModel's Pool Utilization column - the
exact scenario this feature exists for: a site-wide aggregate can look
perfectly healthy while one SPECIFIC pool (assigned via VirtualMachine.
storage_uid) is dangerously full, invisible without this column."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.gui.models.storage_table_model import StorageTableModel
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.calculations.thresholds import Thresholds


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _data(model, row, col, role=Qt.ItemDataRole.DisplayRole):
    return model.data(model.index(row, col), role)


def test_nearly_full_pool_shows_warning_marker_and_color():
    pool = Storage.create_default()
    pool.usable_capacity_tb = 10.0
    vm = VirtualMachine.create_default()
    vm.disk_gb = 9000  # 88% of 10TB
    vm.storage_uid = pool.uid

    model = StorageTableModel([pool], vms_provider=lambda: [vm], thresholds_provider=Thresholds)

    text = _data(model, 0, 8)
    assert "\u26a0" in text
    assert "88%" in text
    assert model.data(model.index(0, 8), Qt.ItemDataRole.ForegroundRole) is not None


def test_lightly_used_pool_shows_no_warning():
    pool = Storage.create_default()
    pool.usable_capacity_tb = 10.0
    vm = VirtualMachine.create_default()
    vm.disk_gb = 500
    vm.storage_uid = pool.uid

    model = StorageTableModel([pool], vms_provider=lambda: [vm], thresholds_provider=Thresholds)

    text = _data(model, 0, 8)
    assert "\u26a0" not in text
    assert model.data(model.index(0, 8), Qt.ItemDataRole.ForegroundRole) is None


def test_pool_with_no_usable_capacity_shows_dash():
    pool = Storage.create_default()
    pool.usable_capacity_tb = 0.0

    model = StorageTableModel([pool])

    assert _data(model, 0, 8) == "-"


def test_pool_with_no_assigned_vms_shows_zero_percent():
    pool = Storage.create_default()
    pool.usable_capacity_tb = 10.0

    model = StorageTableModel([pool], vms_provider=lambda: [])

    assert _data(model, 0, 8) == "0.00 TB (0%)"


def test_unassigned_vms_never_count_toward_any_pool():
    pool = Storage.create_default()
    pool.usable_capacity_tb = 10.0
    unassigned_vm = VirtualMachine.create_default()
    unassigned_vm.disk_gb = 9000
    # storage_uid left at default "" - not assigned

    model = StorageTableModel([pool], vms_provider=lambda: [unassigned_vm], thresholds_provider=Thresholds)

    assert _data(model, 0, 8) == "0.00 TB (0%)"


def test_two_pools_at_the_same_site_are_tracked_independently():
    """The exact scenario from the design discussion - one pool nearly
    full, another barely used, both at the same site."""
    pool_a = Storage.create_default()
    pool_a.name = "Pool A"
    pool_a.usable_capacity_tb = 10.0
    pool_b = Storage.create_default()
    pool_b.name = "Pool B"
    pool_b.usable_capacity_tb = 10.0
    vm_a = VirtualMachine.create_default()
    vm_a.disk_gb = 9000
    vm_a.storage_uid = pool_a.uid
    vm_b = VirtualMachine.create_default()
    vm_b.disk_gb = 500
    vm_b.storage_uid = pool_b.uid

    model = StorageTableModel(
        [pool_a, pool_b], vms_provider=lambda: [vm_a, vm_b], thresholds_provider=Thresholds,
    )

    assert "\u26a0" in _data(model, 0, 8)
    assert "\u26a0" not in _data(model, 1, 8)


def test_storage_page_refreshes_pool_column_on_vm_change():
    from src.services.project_service import ProjectService
    from src.gui.pages.storage_page import StoragePage

    service = ProjectService()
    pool = Storage.create_default()
    pool.usable_capacity_tb = 10.0
    service.add_storage(pool)
    page = StoragePage(service)

    assert _data(page.model, 0, 8) == "0.00 TB (0%)"

    vm = VirtualMachine.create_default()
    vm.disk_gb = 9000
    vm.storage_uid = pool.uid
    service.add_vm(vm)

    assert "88%" in _data(page.model, 0, 8)
