"""Tests for the Attention Needed aggregation - deliberately doesn't
re-test the underlying calculations (CPU/RAM/Storage status, N+1, DR
readiness, backup compliance, maintenance expiry all have their own
test files) - just that this module correctly SELECTS and FORMATS the
Warning/Critical ones into one list."""

from datetime import date

from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.failover_assignment import FailoverAssignment
from src.calculations.thresholds import Thresholds, Status
from src.calculations.attention import compute_attention_items


def _server(site=PRIMARY, sockets=1, cores_per_socket=1, ram_gb=0):
    s = Server.create_default()
    s.site = site
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.hyperthreading_enabled = False
    s.threads_per_core = 1
    s.ram_gb = ram_gb
    return s


def _vm(site=PRIMARY, vcpu=1, ram_gb=1, disk_gb=1, powered_on=True):
    vm = VirtualMachine.create_default()
    vm.site = site
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    vm.disk_gb = disk_gb
    vm.powered_on = powered_on
    return vm


def test_empty_project_has_no_attention_items():
    assert compute_attention_items(ClusterProject(), Thresholds()) == []


def test_healthy_project_has_no_attention_items():
    project = ClusterProject()
    project.servers.append(_server(sockets=2, cores_per_socket=8, ram_gb=256))
    project.servers.append(_server(sockets=2, cores_per_socket=8, ram_gb=256))
    project.vms.append(_vm(vcpu=2, ram_gb=8, disk_gb=50))
    storage = Storage.create_default()
    storage.site = PRIMARY
    storage.raw_capacity_tb = 10
    storage.usable_capacity_tb = 8
    project.storages.append(storage)
    project.backup_destinations.append(BackupDestination(
        uid="1", name="local", site=PRIMARY, destination_type="Disk Appliance",
        backup_software="Veeam", raw_capacity_tb=10, dedup_ratio=1,
        is_offsite=False, is_immutable=False,
    ))
    project.backup_destinations.append(BackupDestination(
        uid="2", name="cloud", site=PRIMARY, destination_type="Offsite",
        backup_software="Veeam", raw_capacity_tb=10, dedup_ratio=1,
        is_offsite=True, is_immutable=True,
    ))

    items = compute_attention_items(project, Thresholds())

    assert items == []


def test_ram_critical_status_is_flagged():
    project = ClusterProject()
    project.servers.append(_server(sockets=1, cores_per_socket=4, ram_gb=32))
    project.vms.append(_vm(vcpu=1, ram_gb=64, disk_gb=10))  # way over physical RAM

    items = compute_attention_items(project, Thresholds())

    assert any("RAM utilization" in i.message and i.severity == Status.CRITICAL for i in items)


def test_n_plus_one_failure_is_flagged():
    project = ClusterProject()
    # Single host - losing it means losing everything, always fails N+1
    # when there's any real demand at all.
    project.servers.append(_server(sockets=2, cores_per_socket=8, ram_gb=128))
    project.vms.append(_vm(vcpu=4, ram_gb=64, disk_gb=50))

    items = compute_attention_items(project, Thresholds())

    assert any("would NOT survive losing 1 host" in i.message for i in items)


def test_dr_not_ready_is_flagged_as_critical():
    project = ClusterProject()
    project.servers.append(_server(site=PRIMARY, sockets=2, cores_per_socket=8, ram_gb=256))
    project.servers.append(_server(site=DR, sockets=1, cores_per_socket=2, ram_gb=16))  # tiny DR
    vm = _vm(site=PRIMARY, vcpu=4, ram_gb=64, disk_gb=50)
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 4
    assignment.ram_gb = 64
    assignment.disk_gb = 50
    project.failover_assignments.append(assignment)

    items = compute_attention_items(project, Thresholds())

    assert any(
        "does not have enough capacity for its assigned failover VMs" in i.message
        and i.severity == Status.CRITICAL
        for i in items
    )


def test_backup_gap_is_flagged_only_when_vms_exist():
    project = ClusterProject()
    project.vms.append(_vm())
    # No backup destinations at all

    items = compute_attention_items(project, Thresholds())

    assert any(i.message.startswith("Backup:") for i in items)


def test_backup_gap_not_flagged_for_a_project_with_no_vms():
    project = ClusterProject()
    # No VMs, no backup destinations - nothing to back up yet, shouldn't nag

    items = compute_attention_items(project, Thresholds())

    assert not any(i.message.startswith("Backup:") for i in items)


def test_compliant_backup_is_not_flagged():
    project = ClusterProject()
    project.vms.append(_vm())
    project.backup_destinations.append(BackupDestination(
        uid="1", name="local", site=PRIMARY, destination_type="Disk Appliance",
        backup_software="Veeam", raw_capacity_tb=10, dedup_ratio=1,
        is_offsite=False, is_immutable=False,
    ))
    project.backup_destinations.append(BackupDestination(
        uid="2", name="cloud", site=PRIMARY, destination_type="Offsite",
        backup_software="Veeam", raw_capacity_tb=10, dedup_ratio=1,
        is_offsite=True, is_immutable=True,
    ))

    items = compute_attention_items(project, Thresholds())

    assert not any(i.message.startswith("Backup:") for i in items)


def test_expired_maintenance_item_is_flagged_as_critical():
    project = ClusterProject()
    project.maintenance_items.append(MaintenanceItem(
        uid="1", name="Old License", category="License", cost=100,
        duration_months=12, expiry_date="2020-01-01",
    ))

    items = compute_attention_items(project, Thresholds())

    matches = [i for i in items if "Old License" in i.message]
    assert len(matches) == 1
    assert matches[0].severity == Status.CRITICAL
    assert "expired" in matches[0].message


def test_expiring_soon_maintenance_item_is_flagged_as_warning():
    project = ClusterProject()
    soon = (date.today().toordinal() + 30)
    expiry = date.fromordinal(soon).isoformat()
    project.maintenance_items.append(MaintenanceItem(
        uid="1", name="Soon License", category="License", cost=100,
        duration_months=12, expiry_date=expiry,
    ))

    items = compute_attention_items(project, Thresholds())

    matches = [i for i in items if "Soon License" in i.message]
    assert len(matches) == 1
    assert matches[0].severity == Status.WARNING
    assert "expiring soon" in matches[0].message


def test_maintenance_item_with_no_expiry_date_is_not_flagged():
    project = ClusterProject()
    project.maintenance_items.append(MaintenanceItem(
        uid="1", name="No Date License", category="License", cost=100,
        duration_months=12, expiry_date="",
    ))

    items = compute_attention_items(project, Thresholds())

    assert not any("No Date License" in i.message for i in items)


def test_items_are_sorted_critical_before_warning():
    project = ClusterProject()
    project.maintenance_items.append(MaintenanceItem(
        uid="1", name="Expiring", category="License", cost=100,
        duration_months=12,
        expiry_date=date.fromordinal(date.today().toordinal() + 30).isoformat(),
    ))
    project.maintenance_items.append(MaintenanceItem(
        uid="2", name="Expired", category="License", cost=100,
        duration_months=12, expiry_date="2020-01-01",
    ))

    items = compute_attention_items(project, Thresholds())

    severities = [i.severity for i in items]
    assert severities.index(Status.CRITICAL) < severities.index(Status.WARNING)


def test_stale_failover_assignment_exceeding_vm_size_is_flagged():
    """The exact scenario found from a real uploaded project: an
    assignment reserves MORE than the VM's current size, likely left
    over from before the VM was resized down."""
    project = ClusterProject()
    vm = _vm(vcpu=8, ram_gb=32, disk_gb=500)
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 16  # exceeds the VM's current 8
    assignment.ram_gb = 32
    assignment.disk_gb = 500
    project.failover_assignments.append(assignment)

    items = compute_attention_items(project, Thresholds())

    matches = [i for i in items if "exceeds the VM's current size" in i.message]
    assert len(matches) == 1
    assert matches[0].severity == Status.WARNING


def test_smaller_intentional_failover_footprint_is_never_flagged():
    """A DELIBERATELY smaller DR footprint (the whole point of
    FailoverAssignment supporting a different footprint per site) must
    never be treated as stale."""
    project = ClusterProject()
    vm = _vm(vcpu=16, ram_gb=64, disk_gb=1000)
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 4  # deliberately smaller, budget DR site
    assignment.ram_gb = 16
    assignment.disk_gb = 1000
    project.failover_assignments.append(assignment)

    items = compute_attention_items(project, Thresholds())

    assert not any("exceeds the VM's current size" in i.message for i in items)


def test_exactly_matching_assignment_is_never_flagged():
    project = ClusterProject()
    vm = _vm(vcpu=8, ram_gb=32, disk_gb=500)
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 8
    assignment.ram_gb = 32
    assignment.disk_gb = 500
    project.failover_assignments.append(assignment)

    items = compute_attention_items(project, Thresholds())

    assert not any("exceeds the VM's current size" in i.message for i in items)


def test_vm_disk_demand_without_any_storage_is_flagged_critical():
    """Found from a real uploaded project: VMs with real disk demand,
    but zero Storage entities and zero server-local disk anywhere -
    the app can't verify there's actually anywhere for that data to
    live. Distinct from the ordinary "nothing entered yet" Unknown
    case, which is never flagged."""
    project = ClusterProject()
    project.vms.append(_vm(vcpu=2, ram_gb=8, disk_gb=500))

    items = compute_attention_items(project, Thresholds())

    matches = [i for i in items if "no storage capacity entered anywhere" in i.message]
    assert len(matches) == 1
    assert matches[0].severity == Status.CRITICAL


def test_no_vms_no_storage_is_never_flagged():
    """A genuinely empty site (no VM disk demand at all) must never be
    flagged - this is the ordinary Unknown case."""
    project = ClusterProject()

    items = compute_attention_items(project, Thresholds())

    assert not any("no storage capacity" in i.message for i in items)


def test_vm_disk_demand_with_adequate_storage_is_not_flagged():
    project = ClusterProject()
    project.vms.append(_vm(vcpu=2, ram_gb=8, disk_gb=500))
    storage = Storage.create_default()
    storage.site = PRIMARY
    storage.raw_capacity_tb = 10
    storage.usable_capacity_tb = 8
    project.storages.append(storage)

    items = compute_attention_items(project, Thresholds())

    assert not any("no storage capacity" in i.message for i in items)


def test_confirmed_stale_assignment_is_not_flagged():
    project = ClusterProject()
    vm = _vm(vcpu=8, ram_gb=32, disk_gb=500)
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 16  # exceeds the VM's current 8
    assignment.footprint_confirmed = True  # explicitly acknowledged as intentional
    project.failover_assignments.append(assignment)

    items = compute_attention_items(project, Thresholds())

    assert not any("exceeds the VM's current size" in i.message for i in items)


def test_storage_with_raw_but_zero_usable_is_flagged():
    """The exact scenario reported directly: an HCI storage entry with
    Raw auto-summed to 48TB from linked servers, but Usable left at 0
    (its deliberate reset-on-HCI-checked default) - never filled in
    before saving. Every capacity check uses Usable, never Raw, so this
    entity silently contributes nothing anywhere until fixed."""
    project = ClusterProject()
    storage = Storage.create_default()
    storage.name = "VSAN"
    storage.site = PRIMARY
    storage.raw_capacity_tb = 48.0
    storage.usable_capacity_tb = 0.0
    project.storages.append(storage)

    items = compute_attention_items(project, Thresholds())

    matches = [i for i in items if "Usable Capacity is still 0" in i.message]
    assert len(matches) == 1
    assert "VSAN" in matches[0].message
    assert matches[0].severity == Status.WARNING


def test_storage_with_both_raw_and_usable_set_is_not_flagged():
    project = ClusterProject()
    storage = Storage.create_default()
    storage.name = "ok-storage"
    storage.site = PRIMARY
    storage.raw_capacity_tb = 48.0
    storage.usable_capacity_tb = 24.0
    project.storages.append(storage)

    items = compute_attention_items(project, Thresholds())

    assert not any("Usable Capacity is still 0" in i.message for i in items)


def test_storage_with_neither_raw_nor_usable_is_not_flagged():
    """A brand new, untouched Storage entry (0/0) isn't 'incomplete' in
    the same actionable sense - nothing has been attempted yet."""
    project = ClusterProject()
    storage = Storage.create_default()
    storage.site = PRIMARY
    project.storages.append(storage)

    items = compute_attention_items(project, Thresholds())

    assert not any("Usable Capacity is still 0" in i.message for i in items)


def test_nearly_full_storage_pool_is_flagged_even_though_site_aggregate_is_healthy():
    """The exact scenario this feature exists for: two pools at the
    same site, one nearly full (assigned VMs), one nearly empty - the
    site-wide aggregate looks perfectly healthy while Pool A is a real
    problem the aggregate check alone can never reveal."""
    project = ClusterProject()
    pool_a = Storage.create_default()
    pool_a.name = "Pool A"
    pool_a.site = PRIMARY
    pool_a.usable_capacity_tb = 10.0
    pool_b = Storage.create_default()
    pool_b.name = "Pool B"
    pool_b.site = PRIMARY
    pool_b.usable_capacity_tb = 10.0
    project.storages.append(pool_a)
    project.storages.append(pool_b)

    vm_a = _vm(vcpu=2, ram_gb=8, disk_gb=9000)
    vm_a.storage_uid = pool_a.uid
    vm_b = _vm(vcpu=2, ram_gb=8, disk_gb=500)
    vm_b.storage_uid = pool_b.uid
    project.vms.append(vm_a)
    project.vms.append(vm_b)

    items = compute_attention_items(project, Thresholds())

    pool_items = [i for i in items if "assigned VMs are using" in i.message]
    assert len(pool_items) == 1
    assert "Pool A" in pool_items[0].message
    assert pool_items[0].severity == Status.WARNING


def test_pool_with_no_assigned_vms_is_never_flagged():
    project = ClusterProject()
    pool = Storage.create_default()
    pool.site = PRIMARY
    pool.usable_capacity_tb = 10.0
    project.storages.append(pool)

    items = compute_attention_items(project, Thresholds())

    assert not any("assigned VMs are using" in i.message for i in items)


def test_pool_utilization_severity_matches_storage_thresholds():
    """A ratio past the CRITICAL threshold should be flagged CRITICAL,
    not just WARNING - reusing the same thresholds as the ordinary
    site-wide storage_status check, not a separate hardcoded cutoff."""
    project = ClusterProject()
    pool = Storage.create_default()
    pool.site = PRIMARY
    pool.usable_capacity_tb = 10.0
    project.storages.append(pool)
    vm = _vm(vcpu=2, ram_gb=8, disk_gb=10000)  # 100% - past critical
    vm.storage_uid = pool.uid
    project.vms.append(vm)

    items = compute_attention_items(project, Thresholds())

    pool_items = [i for i in items if "assigned VMs are using" in i.message]
    assert len(pool_items) == 1
    assert pool_items[0].severity == Status.CRITICAL
