"""Tests for the Attention Needed aggregation - deliberately doesn't
re-test the underlying calculations (CPU/RAM/Storage status, N+1, DR
readiness, backup compliance, maintenance expiry all have their own
test files) - just that this module correctly SELECTS and FORMATS the
Warning/Critical ones into one list."""

from datetime import date

from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.server import Server
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
