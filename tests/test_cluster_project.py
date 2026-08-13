from src.models.cluster_project import ClusterProject, PRIMARY
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
