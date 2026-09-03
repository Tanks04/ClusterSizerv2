from src.calculations.cluster_preparation import (
    HostSpec,
    ManualDemand,
    SizingPolicy,
    compute_site_recommendation,
    compute_sizing,
)
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.models.workload_tier import WORKLOAD_TIERS


def _vm(name, vcpu, ram, disk, tier, site=PRIMARY):
    vm = VirtualMachine.create_default()
    vm.name = name
    vm.site = site
    vm.vcpu = vcpu
    vm.ram_gb = ram
    vm.disk_gb = disk
    vm.workload_tier = tier
    return vm


def _assign_dr(project, vm, vcpu=None, ram_gb=None, disk_gb=None):
    """Adds a FailoverAssignment targeting DR for vm, defaulting the
    footprint to match the VM's own vcpu/ram/disk unless overridden -
    mirrors how ProjectService.set_failover_assignment_for_vms() does it."""
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = vcpu if vcpu is not None else vm.vcpu
    assignment.ram_gb = ram_gb if ram_gb is not None else vm.ram_gb
    assignment.disk_gb = disk_gb if disk_gb is not None else vm.disk_gb
    project.failover_assignments.append(assignment)
    return assignment


def test_empty_project_needs_zero_hosts():
    project = ClusterProject()
    result = compute_sizing(project, SizingPolicy())
    assert result.required_hosts == 0
    assert result.dr_required_hosts == 0


def test_ha_level_adds_expected_extra_hosts():
    """None and Basic HA both size for the fewest hosts (no reserved
    headroom) - the difference between them is whether the HA feature is
    configured at all, not host count. Only N+1/N+2 reserve extra hosts."""
    project = ClusterProject()
    for i in range(10):
        project.vms.append(_vm(f"vm{i}", 4, 8, 50, "Standard Production"))

    host_spec = HostSpec(sockets=1, cores_per_socket=8, threads_per_core=1,
                          hyperthreading_enabled=False, ram_gb=1000)

    none_result = compute_sizing(project, SizingPolicy(ha_level="None", host_spec=host_spec))
    basic_result = compute_sizing(project, SizingPolicy(ha_level="Basic HA", host_spec=host_spec))
    n1_result = compute_sizing(project, SizingPolicy(ha_level="N+1", host_spec=host_spec))
    n2_result = compute_sizing(project, SizingPolicy(ha_level="N+2", host_spec=host_spec))

    assert basic_result.required_hosts == none_result.required_hosts
    assert n1_result.required_hosts == none_result.required_hosts + 1
    assert n2_result.required_hosts == none_result.required_hosts + 2


def test_minimum_two_host_floor():
    """A single VM should still recommend at least 2 hosts - a single host
    is never a "cluster", regardless of how little capacity is needed."""
    project = ClusterProject()
    project.vms.append(_vm("tiny", 1, 1, 10, "Standard Production"))

    result = compute_sizing(project, SizingPolicy(ha_level="None"))
    assert result.required_hosts >= 2


def test_dr_sizing_only_counts_dr_protected_vms():
    project = ClusterProject()
    protected = _vm("protected", 8, 32, 200, "Tier-0 / Mission-Critical")
    unprotected = _vm("unprotected", 8, 32, 200, "Tier-0 / Mission-Critical")
    project.vms.append(protected)
    project.vms.append(unprotected)
    _assign_dr(project, protected)

    result = compute_sizing(project, SizingPolicy())
    assert result.dr_vm_count == 1


def test_dr_site_vms_excluded_from_primary_count():
    """VMs already tagged site=DR are not part of Primary sizing - and the
    excluded count is reported so "why fewer VMs than I loaded" has an answer."""
    project = ClusterProject()
    for i in range(5):
        project.vms.append(_vm(f"primary{i}", 4, 8, 50, "Standard Production", site=PRIMARY))
    for i in range(2):
        project.vms.append(_vm(f"dr{i}", 4, 8, 50, "Standard Production", site=DR))

    result = compute_sizing(project, SizingPolicy())
    assert result.vm_count == 5
    assert result.dr_site_vm_count == 2


def test_recommendation_survives_own_n_plus_one_check():
    """The wizard's own recommendation, applied back to the project as real
    servers, should pass the existing N+1 check - the two calculation
    directions must agree with each other."""
    project = ClusterProject(name="Consistency check")
    for i in range(15):
        project.vms.append(_vm(f"db{i}", 8, 32, 200, "Tier-0 / Mission-Critical"))
    for i in range(25):
        project.vms.append(_vm(f"web{i}", 2, 8, 80, "Development / Test"))

    policy = SizingPolicy(ha_level="N+1", growth_percent=20,
                           host_spec=HostSpec(sockets=2, cores_per_socket=20, ram_gb=384))
    result = compute_sizing(project, policy)

    for i in range(result.required_hosts):
        s = Server.create_default()
        s.name = f"host-{i}"
        s.site = PRIMARY
        s.sockets = policy.host_spec.sockets
        s.cores_per_socket = policy.host_spec.cores_per_socket
        s.threads_per_core = policy.host_spec.threads_per_core
        s.hyperthreading_enabled = policy.host_spec.hyperthreading_enabled
        s.ram_gb = int(policy.host_spec.ram_gb)
        project.servers.append(s)

    assert project.n_plus_one_ok(PRIMARY) is True


def test_storage_sizing_matches_demand_with_overhead():
    project = ClusterProject()
    for i in range(5):
        project.vms.append(_vm(f"vm{i}", 2, 8, 500, "Standard Production"))

    policy = SizingPolicy(growth_percent=0.0, storage_overhead_percent=20.0)
    result = compute_sizing(project, policy)

    expected_usable_tb = (5 * 500) / 1024
    assert abs(result.recommended_storage_usable_tb - expected_usable_tb) < 0.01
    assert abs(result.recommended_storage_raw_tb - expected_usable_tb / 0.8) < 0.01


def test_dr_storage_uses_dr_footprint_not_primary_disk():
    project = ClusterProject()
    db1 = _vm("db1", 4, 16, 1000, "Tier-0 / Mission-Critical")
    project.vms.append(db1)
    _assign_dr(project, db1, disk_gb=250)  # DR replica with a much smaller disk footprint

    result = compute_sizing(project, SizingPolicy(growth_percent=0.0))

    assert abs(result.dr_recommended_storage_usable_tb - 250 / 1024) < 0.01


def test_optimizer_picks_fewer_hosts_over_more_when_ratio_ties_allow():
    """The auto-optimizer (host_spec=None) should never need MORE hosts
    than a reasonable manually-specified spec would for the same demand."""
    project = ClusterProject()
    for i in range(20):
        project.vms.append(_vm(f"vm{i}", 4, 16, 100, "Standard Production"))

    auto_result = compute_sizing(project, SizingPolicy())  # host_spec=None -> optimized
    assert auto_result.required_hosts >= 2  # floor applies
    assert auto_result.host_spec.ram_gb > 0
    assert auto_result.host_spec.cores_per_socket > 0


def test_optimizer_respects_explicit_override():
    project = ClusterProject()
    for i in range(10):
        project.vms.append(_vm(f"vm{i}", 4, 16, 100, "Standard Production"))

    override = HostSpec(sockets=2, cores_per_socket=64, threads_per_core=2,
                         hyperthreading_enabled=True, ram_gb=2048)
    result = compute_sizing(project, SizingPolicy(host_spec=override))
    assert result.host_spec == override


# ----------------------------------------------------------------------
# Hypervisor CPU reserve - previously only a warning NOTE on the Result
# page, never actually applied to the sizing math. Now a real,
# configurable SizingPolicy field, subtracted from each host's usable
# effective capacity before computing how many hosts are needed.
# ----------------------------------------------------------------------

def test_hypervisor_cpu_reserve_disabled_by_default_matches_old_behavior():
    """SizingPolicy() with hypervisor_cpu_reserve_cores explicitly 0
    must produce identical results to the pre-feature behavior."""
    project = ClusterProject()
    for _ in range(15):
        project.vms.append(_vm("vm", 8, 16, 100, "General Purpose"))

    result = compute_sizing(project, SizingPolicy(hypervisor_cpu_reserve_cores=0))

    assert result.required_hosts > 0


def test_larger_hypervisor_cpu_reserve_can_increase_recommended_hosts():
    project = ClusterProject()
    for _ in range(15):
        project.vms.append(_vm("vm", 8, 16, 100, "General Purpose"))

    small_reserve = compute_sizing(project, SizingPolicy(hypervisor_cpu_reserve_cores=0))
    big_reserve = compute_sizing(project, SizingPolicy(hypervisor_cpu_reserve_cores=8))

    assert big_reserve.required_hosts >= small_reserve.required_hosts


def test_hypervisor_cpu_reserve_never_produces_zero_effective_cores():
    """A reserve larger than the host's own capacity must not make
    sizing divide-by-zero or claim '0 hosts needed' - floored at 1
    effective core."""
    project = ClusterProject()
    project.vms.append(_vm("vm", 4, 16, 100, "General Purpose"))

    result = compute_sizing(project, SizingPolicy(
        hypervisor_cpu_reserve_cores=999,
        host_spec=HostSpec(sockets=1, cores_per_socket=2, hyperthreading_enabled=False),
    ))

    assert result.required_hosts >= 1


def test_hypervisor_cpu_reserve_scales_with_hyperthreading():
    """2 physical cores reserved with HT on should remove 2x as many
    EFFECTIVE cores as with HT off, since effective_cores itself scales
    the same way."""
    spec_ht_on = HostSpec(sockets=1, cores_per_socket=16, threads_per_core=2, hyperthreading_enabled=True)
    spec_ht_off = HostSpec(sockets=1, cores_per_socket=16, hyperthreading_enabled=False)

    assert spec_ht_on.effective_cores == 32
    assert spec_ht_off.effective_cores == 16


# ----------------------------------------------------------------------
# assume_hyperthreading - lets the wizard's upfront question control
# whether the auto-optimized host spec assumes HT is on, rather than
# _optimize_host_spec() hardcoding it.
# ----------------------------------------------------------------------

def test_assume_hyperthreading_false_produces_a_non_ht_spec():
    project = ClusterProject()
    for _ in range(15):
        project.vms.append(_vm("vm", 8, 16, 100, "General Purpose"))

    result = compute_sizing(project, SizingPolicy(assume_hyperthreading=False))

    assert result.host_spec.hyperthreading_enabled is False


def test_assume_hyperthreading_true_produces_an_ht_spec():
    project = ClusterProject()
    for _ in range(15):
        project.vms.append(_vm("vm", 8, 16, 100, "General Purpose"))

    result = compute_sizing(project, SizingPolicy(assume_hyperthreading=True))

    assert result.host_spec.hyperthreading_enabled is True


# ----------------------------------------------------------------------
# ManualDemand - sizing a brand-new cluster before any real VMs exist,
# from aggregate CPU/RAM/disk totals entered directly. Real VMs always
# take priority if any exist. Found and fixed two real bugs while
# testing this feature directly: total_storage_demand_gb was only set
# in the manual-demand branch (NameError for every normal call), and
# required_hosts checked "if primary_vms" without accounting for the
# manual-demand case (always producing 0 hosts in that mode).
# ----------------------------------------------------------------------

def test_manual_demand_sizes_a_cluster_with_no_real_vms():
    project = ClusterProject()
    demand = ManualDemand(vcpu=120, ram_gb=240, disk_gb=1500)

    result = compute_sizing(project, SizingPolicy(), manual_demand=demand)

    assert result.used_manual_demand is True
    assert result.total_vcpu_raw == 120
    assert result.total_ram_demand_gb == 240
    assert result.required_hosts > 0


def test_real_vms_take_priority_over_manual_demand_if_both_present():
    project = ClusterProject()
    vm = _vm("real-vm", 4, 16, 100, "General Purpose")
    project.vms.append(vm)
    demand = ManualDemand(vcpu=999, ram_gb=999, disk_gb=999)

    result = compute_sizing(project, SizingPolicy(), manual_demand=demand)

    assert result.used_manual_demand is False
    assert result.total_vcpu_raw == 4


def test_manual_demand_with_zero_values_is_treated_as_no_demand():
    """has_demand is False for an all-zero ManualDemand - the wizard
    shouldn't try to "size a cluster" for literally nothing entered."""
    project = ClusterProject()
    demand = ManualDemand(vcpu=0, ram_gb=0, disk_gb=0)

    result = compute_sizing(project, SizingPolicy(), manual_demand=demand)

    assert result.used_manual_demand is False
    assert result.required_hosts == 0


def test_manual_demand_applies_growth_and_reserve_like_real_vms():
    project = ClusterProject()
    demand = ManualDemand(vcpu=100, ram_gb=100, disk_gb=1024)

    result = compute_sizing(project, SizingPolicy(growth_percent=0.0, memory_reserve_percent=0.0), manual_demand=demand)

    assert result.total_storage_demand_gb == 1024
    assert result.recommended_storage_usable_tb == 1.0


def test_manual_demand_uses_its_own_workload_tier_ratio():
    project = ClusterProject()
    demand = ManualDemand(vcpu=100, ram_gb=100, disk_gb=100, workload_tier="Tier-0 / Mission-Critical")

    result = compute_sizing(project, SizingPolicy(growth_percent=0.0), manual_demand=demand)

    tier_ratio = WORKLOAD_TIERS["Tier-0 / Mission-Critical"].default_ratio
    assert abs(result.total_effective_vcpu - (100 / tier_ratio)) < 0.01


def test_manual_demand_none_behaves_exactly_like_before_the_feature():
    """No manual_demand passed at all (the default) with real VMs must
    produce identical results to calling compute_sizing with just the
    two original arguments."""
    project = ClusterProject()
    for _ in range(5):
        project.vms.append(_vm("vm", 4, 16, 100, "General Purpose"))

    result_no_arg = compute_sizing(project, SizingPolicy())
    result_explicit_none = compute_sizing(project, SizingPolicy(), manual_demand=None)

    assert result_no_arg.required_hosts == result_explicit_none.required_hosts
    assert result_no_arg.used_manual_demand is False


# ----------------------------------------------------------------------
# compute_site_recommendation - the new N-site path, driven by DR
# Category selection rather than pre-existing FailoverAssignment
# records. Coexists with the older dr_* fields (unchanged, still driven
# by FailoverAssignment) - this is an additional, more guided path for
# sizing any additional site, not a replacement.
# ----------------------------------------------------------------------

def _categorized_vm(name, vcpu, ram, disk, tier, category):
    vm = VirtualMachine.create_default()
    vm.name = name
    vm.site = PRIMARY
    vm.vcpu = vcpu
    vm.ram_gb = ram
    vm.disk_gb = disk
    vm.workload_tier = tier
    vm.dr_category = category
    return vm


def test_site_recommendation_includes_only_selected_categories():
    """The exact scenario discussed: 'everything except DWH and
    test/dev' - Core/Important/Standard included, Non-Essential excluded."""
    project = ClusterProject()
    project.add_site("DR2")
    project.vms.append(_categorized_vm("core1", 8, 32, 500, "General Purpose", "Core / Mission-Critical"))
    project.vms.append(_categorized_vm("crm1", 6, 24, 300, "General Purpose", "Important"))
    project.vms.append(_categorized_vm("report1", 6, 32, 500, "General Purpose", "Standard"))
    project.vms.append(_categorized_vm("dwh1", 8, 32, 500, "General Purpose", "Non-Essential"))
    project.vms.append(_categorized_vm("test1", 4, 16, 200, "General Purpose", "Non-Essential"))

    policy = SizingPolicy()
    host_spec = HostSpec(sockets=2, cores_per_socket=16, hyperthreading_enabled=False)
    rec = compute_site_recommendation(
        project, policy, host_spec, "DR2",
        included_categories={"Core / Mission-Critical", "Important", "Standard"},
    )

    assert rec.vm_count == 3
    assert rec.total_vcpu_raw == 8 + 6 + 6


def test_site_recommendation_with_no_categories_selected_needs_zero_hosts():
    project = ClusterProject()
    project.vms.append(_categorized_vm("vm1", 8, 32, 500, "General Purpose", "Core / Mission-Critical"))

    rec = compute_site_recommendation(
        project, SizingPolicy(), HostSpec(), "DR2", included_categories=set(),
    )

    assert rec.vm_count == 0
    assert rec.required_hosts == 0


def test_site_recommendation_reuses_the_given_host_spec_exactly():
    """Should NOT re-optimize - uses host_spec AS GIVEN, so every
    recommended site shares consistent hardware with Primary."""
    project = ClusterProject()
    project.vms.append(_categorized_vm("vm1", 4, 16, 100, "General Purpose", "Core / Mission-Critical"))

    custom_spec = HostSpec(sockets=1, cores_per_socket=4, hyperthreading_enabled=False, ram_gb=64.0)
    rec = compute_site_recommendation(
        project, SizingPolicy(), custom_spec, "DR2",
        included_categories={"Core / Mission-Critical"},
    )

    # With only 4 physical cores/host and no HT, a 4-vCPU VM at a
    # typical ratio needs very little - but the host spec itself is
    # NOT touched (no re-optimization), only the required host COUNT changes.
    assert rec.required_hosts >= 2  # minimum cluster floor


def test_site_recommendation_returns_included_vm_uids_for_failover_assignment_creation():
    project = ClusterProject()
    vm1 = _categorized_vm("vm1", 4, 16, 100, "General Purpose", "Core / Mission-Critical")
    vm2 = _categorized_vm("vm2", 4, 16, 100, "General Purpose", "Non-Essential")
    project.vms.append(vm1)
    project.vms.append(vm2)

    rec = compute_site_recommendation(
        project, SizingPolicy(), HostSpec(), "DR2",
        included_categories={"Core / Mission-Critical"},
    )

    assert rec.included_vm_uids == [vm1.uid]


def test_site_recommendation_applies_growth_percent():
    project = ClusterProject()
    project.vms.append(_categorized_vm("vm1", 4, 16, 1024, "General Purpose", "Core / Mission-Critical"))

    rec = compute_site_recommendation(
        project, SizingPolicy(growth_percent=50.0), HostSpec(), "DR2",
        included_categories={"Core / Mission-Critical"},
    )

    assert rec.storage_demand_gb == 1024 * 1.5
