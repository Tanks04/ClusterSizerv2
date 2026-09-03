"""Tests for StoragePool-entity-level demand/utilization calculations
(pool_demand_gb/pool_utilization_ratio) - distinct from the existing
array-level ones (storage_pool_demand_gb/storage_pool_utilization_
ratio), which stay unaffected by whether VMs are further split across
sub-pools within that array.
"""

from src.models.cluster_project import ClusterProject, PRIMARY
from src.models.storage import Storage, StoragePool
from src.models.virtual_machine import VirtualMachine


def _project_with_pools():
    p = ClusterProject()
    storage = Storage.create_default()
    pool1 = StoragePool(uid="p1", name="SSD-Tier", usable_capacity_tb=1.0)
    pool2 = StoragePool(uid="p2", name="SATA-Tier", usable_capacity_tb=2.0)
    storage.pools = [pool1, pool2]
    p.storages.append(storage)
    return p, storage, pool1, pool2


def test_pool_demand_sums_only_vms_on_that_pool():
    p, storage, pool1, pool2 = _project_with_pools()
    vm1 = VirtualMachine.create_default()
    vm1.disk_gb = 500
    vm1.storage_uid = storage.uid
    vm1.storage_pool_uid = "p1"
    vm2 = VirtualMachine.create_default()
    vm2.disk_gb = 200
    vm2.storage_uid = storage.uid
    vm2.storage_pool_uid = "p2"
    p.vms.extend([vm1, vm2])

    assert p.pool_demand_gb("p1") == 500
    assert p.pool_demand_gb("p2") == 200


def test_pool_utilization_ratio():
    p, storage, pool1, pool2 = _project_with_pools()
    vm = VirtualMachine.create_default()
    vm.disk_gb = 512
    vm.storage_uid = storage.uid
    vm.storage_pool_uid = "p1"
    p.vms.append(vm)

    # pool1 usable = 1.0 TB = 1024 GB
    assert abs(p.pool_utilization_ratio(pool1) - 512 / 1024) < 0.0001


def test_pool_utilization_none_when_pool_usable_is_zero():
    empty_pool = StoragePool(uid="p3", name="Empty", usable_capacity_tb=0.0)
    p = ClusterProject()

    assert p.pool_utilization_ratio(empty_pool) is None


def test_vms_without_a_pool_assignment_dont_count_toward_any_pool():
    p, storage, pool1, pool2 = _project_with_pools()
    vm = VirtualMachine.create_default()
    vm.disk_gb = 500
    vm.storage_uid = storage.uid
    # storage_pool_uid left blank - whole-array aggregate only
    p.vms.append(vm)

    assert p.pool_demand_gb("p1") == 0
    assert p.pool_demand_gb("p2") == 0


def test_array_level_demand_unaffected_by_sub_pool_split():
    """The existing array-wide storage_pool_demand_gb must keep
    counting every VM on the array regardless of which sub-pool (if
    any) each one is further assigned to."""
    p, storage, pool1, pool2 = _project_with_pools()
    vm1 = VirtualMachine.create_default()
    vm1.disk_gb = 500
    vm1.storage_uid = storage.uid
    vm1.storage_pool_uid = "p1"
    vm2 = VirtualMachine.create_default()
    vm2.disk_gb = 300
    vm2.storage_uid = storage.uid
    vm2.storage_pool_uid = "p2"
    vm3 = VirtualMachine.create_default()
    vm3.disk_gb = 200
    vm3.storage_uid = storage.uid
    # vm3 has no sub-pool at all
    p.vms.extend([vm1, vm2, vm3])

    assert p.storage_pool_demand_gb(storage.uid) == 1000


def test_two_different_pools_track_independently():
    """The exact scenario motivating this feature: one pool can be
    hot while a sibling pool on the same array is fine."""
    p, storage, pool1, pool2 = _project_with_pools()
    vm = VirtualMachine.create_default()
    vm.disk_gb = 1024  # fills pool1 (1 TB usable) completely
    vm.storage_uid = storage.uid
    vm.storage_pool_uid = "p1"
    p.vms.append(vm)

    assert p.pool_utilization_ratio(pool1) == 1.0
    assert p.pool_utilization_ratio(pool2) == 0.0
