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
