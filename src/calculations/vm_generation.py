"""Generates N VirtualMachine records from aggregate totals - for the
New Project Wizard's "I don't want to enter VMs one by one yet, just
give me a rough starting point" step. Splits the totals evenly across
the requested count, generic names (vm-01, vm-02, ...) meant to be
renamed by the person afterward. Deliberately does NOT invent per-VM
detail (OS, workload tier, etc.) beyond the numbers actually given -
this is a starting point, not a fabricated inventory.
"""

from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


def _split_evenly_int(total: int, count: int) -> list[int]:
    """Splits an integer total across count parts as evenly as
    possible - the remainder (if total doesn't divide evenly) goes one
    each to the first `remainder` parts, so the parts always sum back
    to exactly `total`."""
    if count <= 0:
        return []
    base = total // count
    remainder = total - base * count
    return [base + (1 if i < remainder else 0) for i in range(count)]


def generate_vms(
    count: int, total_vcpu: int, total_ram_gb: float, total_disk_gb: float, site: str,
) -> list[VirtualMachine]:
    """Returns count VMs named vm-01..vm-NN at the given site, with
    vCPU/RAM/Disk evenly split from the given totals. Returns an empty
    list for count <= 0 (nothing to generate)."""
    if count <= 0:
        return []

    vcpu_splits = _split_evenly_int(total_vcpu, count)
    ram_per_vm = total_ram_gb / count
    disk_per_vm = total_disk_gb / count

    vms = []
    name_width = len(str(count))
    for i in range(count):
        vm = VirtualMachine.create_default()
        vm.name = f"vm-{i + 1:0{max(2, name_width)}d}"
        vm.site = site
        vm.vcpu = vcpu_splits[i]
        vm.ram_gb = ram_per_vm
        vm.disk_gb = disk_per_vm
        vms.append(vm)
    return vms


def generate_servers(
    count: int, sockets: int, cores_per_socket: int, ram_gb: int, site: str,
) -> list[Server]:
    """Returns count IDENTICAL servers named server-01..server-NN at the
    given site - unlike generate_vms, this does NOT split an aggregate
    total, since buying N identical physical hosts is how hardware
    actually gets purchased (each one has the SAME sockets/cores/RAM,
    not a fraction of some total). Returns an empty list for count <= 0."""
    if count <= 0:
        return []

    name_width = len(str(count))
    servers = []
    for i in range(count):
        server = Server.create_default()
        server.name = f"server-{i + 1:0{max(2, name_width)}d}"
        server.site = site
        server.sockets = sockets
        server.cores_per_socket = cores_per_socket
        server.ram_gb = ram_gb
        servers.append(server)
    return servers
