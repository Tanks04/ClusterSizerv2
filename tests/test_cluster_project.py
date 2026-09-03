from src.calculations.thresholds import Thresholds
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


def _server(name, ram_gb, sockets, cores_per_socket):
    s = Server.create_default()
    s.name = name
    s.site = PRIMARY
    s.ram_gb = ram_gb
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.threads_per_core = 1
    s.hyperthreading_enabled = False
    return s


def _vm(vcpu, ram_gb):
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    vm.powered_on = True
    return vm


def test_n_plus_one_heterogeneous_cpu():
    """RAM-largest host is not the cores-largest host - demand fits after
    losing the RAM-largest one but not after losing the cores-largest one."""
    project = ClusterProject()
    project.servers.append(_server("A", ram_gb=1024, sockets=1, cores_per_socket=16))  # 16 cores
    project.servers.append(_server("B", ram_gb=256, sockets=4, cores_per_socket=16))    # 64 cores
    project.vms.append(_vm(vcpu=50, ram_gb=10))

    assert project.n_plus_one_ok(PRIMARY) is False


def test_n_plus_one_homogeneous_survives():
    project = ClusterProject()
    for i in range(3):
        project.servers.append(_server(f"s{i}", ram_gb=512, sockets=2, cores_per_socket=16))
    project.vms.append(_vm(vcpu=40, ram_gb=800))

    assert project.n_plus_one_ok(PRIMARY) is True


def test_n_plus_one_no_servers_returns_none():
    project = ClusterProject()
    assert project.n_plus_one_ok(PRIMARY) is None


def test_n_plus_one_single_server_is_false():
    project = ClusterProject()
    project.servers.append(_server("solo", ram_gb=512, sockets=2, cores_per_socket=16))
    project.vms.append(_vm(vcpu=1, ram_gb=1))

    assert project.n_plus_one_ok(PRIMARY) is False


def test_n_plus_one_cpu_allows_configured_oversubscription_tolerance():
    """CPU (unlike RAM) is expected to run oversubscribed day to day - N+1
    should ask "does it stay within my configured comfort threshold after
    losing a host", not demand literal 1:1 vCPU:pCPU."""
    project = ClusterProject()
    for name in ("A", "B"):
        s = _server(name, ram_gb=2048, sockets=2, cores_per_socket=24)
        project.servers.append(s)
    for i in range(20):
        vm = _vm(vcpu=9, ram_gb=4)
        project.vms.append(vm)

    # 180 vCPU demand, losing one 48-core host leaves 48 physical cores -
    # strict 1:1 fails (180 > 48), a realistic 4:1 tolerance should pass
    # (48 * 4 = 192 >= 180).
    assert project.n_plus_one_ok(PRIMARY) is False  # default stays strict
    assert project.n_plus_one_ok(PRIMARY, cpu_warning_ratio=4.0) is True


def test_n_plus_one_ram_never_gets_oversubscription_tolerance():
    """Unlike CPU, RAM headroom should stay strict regardless of any
    ratio passed in - RAM overcommit is a fundamentally different risk."""
    project = ClusterProject()
    for name in ("A", "B"):
        s = _server(name, ram_gb=512, sockets=2, cores_per_socket=64)
        project.servers.append(s)
    vm = _vm(vcpu=1, ram_gb=600)  # more RAM than either host alone has
    project.vms.append(vm)

    assert project.n_plus_one_ok(PRIMARY, cpu_warning_ratio=100.0) is False


def test_disabled_server_excluded_from_capacity_but_stays_in_project():
    project = ClusterProject()
    a = _server("A", ram_gb=512, sockets=2, cores_per_socket=24)
    b = _server("B", ram_gb=512, sockets=2, cores_per_socket=24)
    project.servers += [a, b]

    assert len(project.servers_at(PRIMARY)) == 2
    assert project.physical_cores(PRIMARY) == 96

    b.enabled = False

    assert len(project.servers_at(PRIMARY)) == 1
    assert project.physical_cores(PRIMARY) == 48
    assert b in project.servers  # still there, just excluded from capacity math
    assert project.server_count == 1

    b.enabled = True
    assert project.physical_cores(PRIMARY) == 96


def test_n_plus_one_check_reports_ram_only_shortfall():
    """When only RAM is short (CPU is fine within tolerance), the detail
    should say so specifically instead of a blanket failure."""
    project = ClusterProject()
    a = _server("A", ram_gb=512, sockets=2, cores_per_socket=24)
    b = _server("B", ram_gb=512, sockets=2, cores_per_socket=24)
    project.servers += [a, b]
    project.vms.append(_vm(vcpu=10, ram_gb=600))  # tiny CPU demand, big RAM demand

    check = project.n_plus_one_check(PRIMARY, cpu_warning_ratio=4.0)
    assert check.ram_ok is False
    assert check.cpu_ok is True
    assert check.ram_shortfall_gb > 0
    assert check.cpu_shortfall_effective_cores == 0
    assert check.ok is False


def test_n_plus_one_check_matches_n_plus_one_ok():
    project = ClusterProject()
    a = _server("A", ram_gb=1024, sockets=1, cores_per_socket=16)
    b = _server("B", ram_gb=256, sockets=4, cores_per_socket=16)
    project.servers += [a, b]
    project.vms.append(_vm(vcpu=50, ram_gb=10))

    check = project.n_plus_one_check(PRIMARY)
    assert check.ok == project.n_plus_one_ok(PRIMARY)


def test_n_plus_one_check_none_for_empty_site():
    project = ClusterProject()
    assert project.n_plus_one_check(PRIMARY) is None


def test_hyperthreading_summary_all_sites_vs_per_site():
    """S22: hyperthreading_summary(site=None) covers all sites (what
    ServersPage's global toggle needs), a specific site matches the
    existing hyperthreading_state() behavior."""
    from src.models.cluster_project import DR

    project = ClusterProject()
    a = _server("A", ram_gb=512, sockets=2, cores_per_socket=16)
    a.hyperthreading_enabled = True
    b = _server("B", ram_gb=512, sockets=2, cores_per_socket=16)
    b.hyperthreading_enabled = False
    c = _server("C", ram_gb=512, sockets=2, cores_per_socket=16)
    c.site = DR
    c.hyperthreading_enabled = True
    project.servers += [a, b, c]

    assert project.hyperthreading_state(PRIMARY) == "mixed"
    assert project.hyperthreading_state(DR) == "all_on"

    all_sites = project.hyperthreading_summary()
    assert all_sites.state == "mixed"
    assert all_sites.on_count == 2
    assert all_sites.total_count == 3

    dr_only = project.hyperthreading_summary(DR)
    assert dr_only.state == "all_on"
    assert dr_only.on_count == 1
    assert dr_only.total_count == 1


def test_hyperthreading_summary_empty_project():
    project = ClusterProject()
    summary = project.hyperthreading_summary()
    assert summary.state == "no_servers"
    assert summary.on_count == 0
    assert summary.total_count == 0


def test_default_deployment_model_is_on_premise_for_both_sites():
    project = ClusterProject()
    assert project.deployment_model_for("Primary") == "On-Premise"
    assert project.deployment_model_for("DR") == "On-Premise"
    assert project.is_cloud("Primary") is False
    assert project.is_cloud("DR") is False


def test_deployment_model_for_looks_up_the_right_site():
    from src.models.cluster_project import DR

    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")

    assert project.deployment_model_for(PRIMARY) == "On-Premise"
    assert project.deployment_model_for(DR) == "Cloud"


def test_is_cloud_reflects_per_site_setting_independently():
    """The exact scenario this exists for - DRaaS: on-prem Primary,
    cloud DR, in the same project."""
    from src.models.cluster_project import DR

    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")

    assert project.is_cloud(PRIMARY) is False
    assert project.is_cloud(DR) is True


# ----------------------------------------------------------------------
# failover_cpu_ok / failover_ready - a real bug reported directly: the
# check compared raw physical_cores against raw vCPU demand (effectively
# requiring near-1:1 provisioning) instead of using the same CPU
# oversubscription ratio threshold as ordinary CPU status - so a
# perfectly healthy, normally-oversubscribed site (e.g. 3.75:1, well
# under a 4:1 warning threshold) got falsely flagged as "not enough
# capacity for its assigned failover VMs."
# ----------------------------------------------------------------------

def test_failover_cpu_ok_true_for_a_healthy_oversubscribed_ratio():
    """The exact reported scenario: 15 VMs / 120 vCPU on 2 hosts with 32
    physical cores (HT-adjusted) - a 3.75:1 ratio, comfortably under the
    default 4:1 warning threshold, must NOT be flagged as failing."""
    project = ClusterProject()
    for _ in range(2):
        s = Server.create_default()
        s.site = PRIMARY
        s.sockets = 1
        s.cores_per_socket = 8
        s.hyperthreading_enabled = True
        s.threads_per_core = 2
        s.ram_gb = 256
        project.servers.append(s)
    for _ in range(15):
        vm = VirtualMachine.create_default()
        vm.site = PRIMARY
        vm.vcpu = 8
        vm.ram_gb = 16
        project.vms.append(vm)

    assert project.physical_cores(PRIMARY) == 32
    assert project.vm_vcpu_demand(PRIMARY) == 120

    thresholds = Thresholds()
    assert project.failover_cpu_ok(PRIMARY, thresholds) is True


def test_failover_cpu_ok_false_for_a_genuinely_critical_ratio():
    """A real mismatch (10:1, well past the 6:1 default critical
    threshold) must still be caught - the fix must not become so
    permissive it stops catching real problems."""
    project = ClusterProject()
    server = Server.create_default()
    server.site = DR
    server.sockets = 1
    server.cores_per_socket = 4
    server.hyperthreading_enabled = False
    project.servers.append(server)
    vm = VirtualMachine.create_default()
    vm.site = PRIMARY
    vm.vcpu = 40
    project.vms.append(vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = vm.uid
    assignment.target_site = DR
    assignment.vcpu = 40
    project.failover_assignments.append(assignment)

    thresholds = Thresholds()
    assert project.failover_cpu_ok(DR, thresholds) is False


def test_failover_cpu_ok_none_with_no_servers_at_site():
    project = ClusterProject()
    assert project.failover_cpu_ok(DR, Thresholds()) is None


# ----------------------------------------------------------------------
# storage_pool_demand_gb / storage_pool_utilization_ratio - opt-in
# per-pool tracking via VirtualMachine.storage_uid. Purely additive -
# the site-wide aggregate stays exactly as it always was, unaffected by
# whether any VM uses this.
# ----------------------------------------------------------------------

def test_storage_pool_demand_sums_only_assigned_vms():
    from src.models.storage import Storage

    project = ClusterProject()
    pool_a = Storage.create_default()
    pool_b = Storage.create_default()
    vm1 = _vm(4, 16)
    vm1.disk_gb = 500
    vm1.storage_uid = pool_a.uid
    vm2 = _vm(4, 16)
    vm2.disk_gb = 300
    vm2.storage_uid = pool_a.uid
    vm3 = _vm(4, 16)
    vm3.disk_gb = 1000
    vm3.storage_uid = pool_b.uid
    project.vms.extend([vm1, vm2, vm3])

    assert project.storage_pool_demand_gb(pool_a.uid) == 800
    assert project.storage_pool_demand_gb(pool_b.uid) == 1000


def test_unassigned_vms_do_not_count_toward_any_pool():
    from src.models.storage import Storage

    project = ClusterProject()
    pool = Storage.create_default()
    vm = _vm(4, 16)
    vm.disk_gb = 500
    # vm.storage_uid left at default "" - not assigned to any pool
    project.vms.append(vm)

    assert project.storage_pool_demand_gb(pool.uid) == 0


def test_storage_pool_utilization_ratio_none_when_usable_is_zero():
    from src.models.storage import Storage

    project = ClusterProject()
    pool = Storage.create_default()
    pool.usable_capacity_tb = 0.0

    assert project.storage_pool_utilization_ratio(pool) is None


def test_storage_pool_reveals_a_problem_the_site_aggregate_hides():
    """The exact scenario this feature exists for: two pools at the
    same site, one nearly full, one nearly empty - the site-wide
    aggregate ratio looks perfectly healthy while Pool A is a real
    problem the aggregate alone can never reveal."""
    from src.models.storage import Storage

    project = ClusterProject()
    pool_a = Storage.create_default()
    pool_a.site = PRIMARY
    pool_a.usable_capacity_tb = 10.0
    pool_b = Storage.create_default()
    pool_b.site = PRIMARY
    pool_b.usable_capacity_tb = 10.0
    project.storages.extend([pool_a, pool_b])

    vm_a = _vm(2, 8)
    vm_a.disk_gb = 9000  # 87% of Pool A - nearly full
    vm_a.storage_uid = pool_a.uid
    vm_b = _vm(2, 8)
    vm_b.disk_gb = 500  # ~5% of Pool B
    vm_b.storage_uid = pool_b.uid
    project.vms.extend([vm_a, vm_b])

    site_ratio = project.storage_utilization_ratio(PRIMARY)
    pool_a_ratio = project.storage_pool_utilization_ratio(pool_a)

    assert site_ratio < 0.5  # aggregate looks fine
    assert pool_a_ratio > 0.85  # but Pool A specifically is nearly full
