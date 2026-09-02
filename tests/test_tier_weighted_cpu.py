"""Tests for tier-weighted "effective" CPU oversubscription - the raw
vCPU:pCore ratio treats every vCPU the same regardless of Workload
Tier, so changing a VM's tier had zero effect on the displayed ratio
(reported directly). Reuses the exact effective-vCPU formula already
established in Cluster Preparation (vm.vcpu / tier_ratio), applied to
the ONGOING/live ratio instead of just the one-time sizing wizard.
"""

from src.models.cluster_project import ClusterProject, PRIMARY
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.models.workload_tier import tier_ratio_for
from src.calculations.attention import compute_attention_items
from src.calculations.thresholds import Thresholds


def _project_with_tier(tier: str, vm_count: int = 20, vcpu_each: int = 10) -> ClusterProject:
    p = ClusterProject()
    for _ in range(2):
        s = Server.create_default()
        s.site = PRIMARY
        s.sockets = 2
        s.cores_per_socket = 16
        s.hyperthreading_enabled = False
        p.servers.append(s)
    for _ in range(vm_count):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = vcpu_each
        vm.workload_tier = tier
        p.vms.append(vm)
    return p


# ----------------------------------------------------------------------
# tier_ratio_for
# ----------------------------------------------------------------------

def test_tier_ratio_for_known_tiers():
    assert tier_ratio_for("Tier-0 / Mission-Critical") == 1.0
    assert tier_ratio_for("Standard Production") == 4.0
    assert tier_ratio_for("Development / Test") == 8.0
    assert tier_ratio_for("High-Density VDI") == 12.0


def test_tier_ratio_for_unknown_falls_back_to_standard_production():
    assert tier_ratio_for("") == 4.0
    assert tier_ratio_for("Some Custom Tier") == 4.0


# ----------------------------------------------------------------------
# ClusterProject.effective_cpu_ratio - the exact reported scenario
# ----------------------------------------------------------------------

def test_all_tier0_effective_ratio_equals_raw_ratio():
    """Tier-0's own ratio is 1.0, so effective == raw for an
    all-Tier-0 site - exactly the case reported directly (3.1:1, no
    matter the tier, because tier had zero effect before this)."""
    project = _project_with_tier("Tier-0 / Mission-Critical")

    raw = project.cpu_oversubscription_ratio(PRIMARY)
    effective = project.effective_cpu_ratio(PRIMARY)

    assert raw == 3.125
    assert effective == 3.125


def test_all_vdi_effective_ratio_much_lower_than_raw():
    project = _project_with_tier("High-Density VDI")

    raw = project.cpu_oversubscription_ratio(PRIMARY)
    effective = project.effective_cpu_ratio(PRIMARY)

    assert raw == 3.125
    assert abs(effective - 3.125 / 12) < 0.001


def test_mixed_tiers_matches_the_worked_example():
    """10 Tier-0 + 10 VDI, 100 vCPU each group, 64 cores - the exact
    scenario worked through by hand: effective vCPU = 100/1 + 100/12 =
    108.33, ratio = 108.33/64 = 1.69."""
    project = ClusterProject()
    for _ in range(2):
        s = Server.create_default()
        s.site = PRIMARY
        s.sockets = 2
        s.cores_per_socket = 16
        s.hyperthreading_enabled = False
        project.servers.append(s)
    for _ in range(10):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = 10
        vm.workload_tier = "Tier-0 / Mission-Critical"
        project.vms.append(vm)
    for _ in range(10):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = 10
        vm.workload_tier = "High-Density VDI"
        project.vms.append(vm)

    effective = project.effective_cpu_ratio(PRIMARY)

    assert abs(effective - (100 / 1 + 100 / 12) / 64) < 0.001


def test_effective_ratio_none_with_no_physical_cores():
    project = ClusterProject()
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    project.vms.append(vm)

    assert project.effective_cpu_ratio(PRIMARY) is None


def test_powered_off_vms_excluded_from_effective_demand():
    project = _project_with_tier("Tier-0 / Mission-Critical", vm_count=1)
    project.vms[0].powered_on = False

    assert project.effective_vcpu_demand(PRIMARY) == 0


# ----------------------------------------------------------------------
# Attention check
# ----------------------------------------------------------------------

def test_all_tier0_triggers_critical_effective_ratio_attention():
    project = _project_with_tier("Tier-0 / Mission-Critical")

    items = compute_attention_items(project, Thresholds())

    tier_items = [i for i in items if "tier-weighted" in i.message]
    assert len(tier_items) == 1
    assert tier_items[0].severity.value == "Critical"
    assert "3.1:1" in tier_items[0].message


def test_all_vdi_triggers_no_effective_ratio_attention():
    project = _project_with_tier("High-Density VDI")

    items = compute_attention_items(project, Thresholds())

    tier_items = [i for i in items if "tier-weighted" in i.message]
    assert tier_items == []


def test_mixed_tiers_names_the_dominant_strict_tier():
    project = ClusterProject()
    for _ in range(2):
        s = Server.create_default()
        s.site = PRIMARY
        s.sockets = 2
        s.cores_per_socket = 16
        s.hyperthreading_enabled = False
        project.servers.append(s)
    for _ in range(10):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = 10
        vm.workload_tier = "Tier-0 / Mission-Critical"
        project.vms.append(vm)
    for _ in range(10):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = 10
        vm.workload_tier = "High-Density VDI"
        project.vms.append(vm)

    items = compute_attention_items(project, Thresholds())

    tier_items = [i for i in items if "tier-weighted" in i.message]
    assert len(tier_items) == 1
    assert "Tier-0 / Mission-Critical" in tier_items[0].message
    assert "50%" in tier_items[0].message
    assert "High (CPU Shares/Reservation)" in tier_items[0].message


def test_healthy_effective_ratio_produces_no_attention_item():
    """A handful of Standard Production VMs on plenty of cores - well
    under both raw and effective thresholds."""
    project = ClusterProject()
    s = Server.create_default()
    s.site = PRIMARY
    s.sockets = 2
    s.cores_per_socket = 32
    s.hyperthreading_enabled = False
    project.servers.append(s)
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    vm.vcpu = 8
    vm.workload_tier = "Standard Production"
    project.vms.append(vm)

    items = compute_attention_items(project, Thresholds())

    assert [i for i in items if "tier-weighted" in i.message] == []


def test_effective_ratio_thresholds_are_fixed_not_configurable():
    """Warning at 1.0, Critical at 1.5 - intrinsic to what 'effective'
    means (Tier-0's own ratio is 1.0), not a Settings-adjustable value
    like the raw CPU thresholds."""
    project = ClusterProject()
    s = Server.create_default()
    s.site = PRIMARY
    s.sockets = 1
    s.cores_per_socket = 10
    s.hyperthreading_enabled = False
    project.servers.append(s)
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    vm.vcpu = 11  # just over 1.0 with Tier-0 (11/10 = 1.1)
    vm.workload_tier = "Tier-0 / Mission-Critical"
    project.vms.append(vm)

    # Even with very lenient (never-fires) global thresholds, the
    # effective-ratio check must still fire - it's not driven by
    # thresholds.cpu_warning_ratio at all.
    lenient = Thresholds()
    lenient.cpu_warning_ratio = 100.0
    lenient.cpu_critical_ratio = 200.0

    items = compute_attention_items(project, lenient)

    tier_items = [i for i in items if "tier-weighted" in i.message]
    assert len(tier_items) == 1
    assert tier_items[0].severity.value == "Warning"


# ----------------------------------------------------------------------
# SiteReport / build_site_report / build_failover_scenario_report
# ----------------------------------------------------------------------

def test_site_report_carries_effective_cpu_fields():
    from src.calculations.sizing import build_site_report

    project = _project_with_tier("Tier-0 / Mission-Critical")

    report = build_site_report(project, PRIMARY, Thresholds())

    assert report.effective_cpu_ratio == 3.125
    assert report.effective_cpu_status.value == "Critical"


def test_failover_scenario_report_carries_effective_cpu_fields():
    from src.models.server import Server as ServerModel
    from src.models.failover_assignment import FailoverAssignment
    from src.calculations.sizing import build_failover_scenario_report
    from src.models.cluster_project import DR

    project = _project_with_tier("Tier-0 / Mission-Critical", vm_count=1, vcpu_each=10)
    dr_server = ServerModel.create_default()
    dr_server.site = DR
    dr_server.sockets = 1
    dr_server.cores_per_socket = 8
    dr_server.hyperthreading_enabled = False
    project.servers.append(dr_server)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = project.vms[0].uid
    assignment.target_site = DR
    assignment.vcpu = 10
    project.failover_assignments.append(assignment)

    report = build_failover_scenario_report(project, DR, Thresholds())

    assert report.effective_cpu_ratio == 10 / 1 / 8


def test_effective_failover_vcpu_demand_scales_by_tier():
    from src.models.server import Server as ServerModel
    from src.models.failover_assignment import FailoverAssignment
    from src.models.cluster_project import DR

    project = ClusterProject()
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    vm.vcpu = 12
    vm.workload_tier = "High-Density VDI"
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 12
    project.failover_assignments.append(assignment)

    # VDI ratio 12.0, so 12 vCPU footprint -> 1.0 effective
    assert project.effective_failover_vcpu_demand(DR) == 1.0


# ----------------------------------------------------------------------
# SiteCapacityWidget - the visible number (the actual reported gap:
# no visible metric anywhere for the person to watch change)
# ----------------------------------------------------------------------

def test_site_capacity_widget_shows_effective_cpu_row():
    import pytest
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.widgets.site_capacity_widget import SiteCapacityWidget
    from src.calculations.sizing import build_site_report

    project = _project_with_tier("Tier-0 / Mission-Critical")
    report = build_site_report(project, PRIMARY, Thresholds())
    widget = SiteCapacityWidget(PRIMARY)

    widget.set_report(report)

    assert widget.effective_cpu_bar.format() == "3.12 : 1"
    assert widget.effective_cpu_badge.text() == "Critical"


def test_site_capacity_widget_effective_row_updates_when_tier_changes():
    import pytest
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.widgets.site_capacity_widget import SiteCapacityWidget
    from src.calculations.sizing import build_site_report

    project = _project_with_tier("Tier-0 / Mission-Critical")
    widget = SiteCapacityWidget(PRIMARY)
    widget.set_report(build_site_report(project, PRIMARY, Thresholds()))
    assert widget.effective_cpu_badge.text() == "Critical"

    for vm in project.vms:
        vm.workload_tier = "High-Density VDI"
    widget.set_report(build_site_report(project, PRIMARY, Thresholds()))

    assert widget.effective_cpu_badge.text() == "OK"
    assert widget.effective_cpu_bar.format() != "3.12 : 1"
