from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.virtual_machine import VirtualMachine
from src.calculations.cluster_preparation import compute_sizing, SizingPolicy, HostSpec


def _vm(name, vcpu, ram, disk, profile, dr=False):
    vm = VirtualMachine.create_default()
    vm.name = name
    vm.site = PRIMARY
    vm.vcpu = vcpu
    vm.ram_gb = ram
    vm.disk_gb = disk
    vm.workload_profile = profile
    vm.dr_protected = dr
    if dr:
        vm.dr_vcpu = vcpu
        vm.dr_ram_gb = ram
        vm.dr_disk_gb = disk
    return vm


def test_empty_project_needs_zero_hosts():
    project = ClusterProject()
    result = compute_sizing(project, SizingPolicy())
    assert result.required_hosts == 0
    assert result.dr_required_hosts == 0


def test_ha_level_adds_expected_extra_hosts():
    project = ClusterProject()
    for i in range(10):
        project.vms.append(_vm(f"vm{i}", 4, 8, 50, "Balanced"))

    host_spec = HostSpec(sockets=1, cores_per_socket=8, threads_per_core=1,
                          hyperthreading_enabled=False, ram_gb=1000)

    none_result = compute_sizing(project, SizingPolicy(ha_level="None", host_spec=host_spec))
    n1_result = compute_sizing(project, SizingPolicy(ha_level="N+1", host_spec=host_spec))
    n2_result = compute_sizing(project, SizingPolicy(ha_level="N+2", host_spec=host_spec))

    assert n1_result.required_hosts == none_result.required_hosts + 1
    assert n2_result.required_hosts == none_result.required_hosts + 2


def test_dr_sizing_only_counts_dr_protected_vms():
    project = ClusterProject()
    project.vms.append(_vm("protected", 8, 32, 200, "CPU Intensive", dr=True))
    project.vms.append(_vm("unprotected", 8, 32, 200, "CPU Intensive", dr=False))

    result = compute_sizing(project, SizingPolicy())
    assert result.dr_vm_count == 1


def test_recommendation_survives_own_n_plus_one_check():
    """The wizard's own recommendation, applied back to the project as real
    servers, should pass the existing N+1 check - the two calculation
    directions must agree with each other."""
    from src.models.server import Server

    project = ClusterProject(name="Consistency check")
    for i in range(15):
        project.vms.append(_vm(f"db{i}", 8, 32, 200, "CPU Intensive"))
    for i in range(25):
        project.vms.append(_vm(f"web{i}", 2, 8, 80, "Light"))

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
        project.vms.append(_vm(f"vm{i}", 2, 8, 500, "Balanced"))

    policy = SizingPolicy(storage_overhead_percent=20.0)
    result = compute_sizing(project, policy)

    expected_usable_tb = (5 * 500) / 1024
    assert abs(result.recommended_storage_usable_tb - expected_usable_tb) < 0.01
    assert abs(result.recommended_storage_raw_tb - expected_usable_tb / 0.8) < 0.01


def test_dr_storage_uses_dr_footprint_not_primary_disk():
    project = ClusterProject()
    project.vms.append(_vm("db1", 4, 16, 1000, "CPU Intensive", dr=True))
    project.vms[0].dr_disk_gb = 250  # DR replica with a much smaller disk footprint

    result = compute_sizing(project, SizingPolicy())

    assert abs(result.dr_recommended_storage_usable_tb - 250 / 1024) < 0.01
