from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.virtual_machine import VirtualMachine
from src.models.failover_assignment import FailoverAssignment
from src.models.server import Server
from src.calculations.cluster_preparation import compute_sizing, SizingPolicy, HostSpec


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
