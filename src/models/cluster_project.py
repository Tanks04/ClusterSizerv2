from dataclasses import dataclass, field

from .server import Server
from .storage import Storage
from .virtual_machine import VirtualMachine
from .network_switch import NetworkSwitch
from .network_connection import NetworkConnection

PRIMARY = "Primary"
DR = "DR"


@dataclass
class ClusterProject:
    """Represents one ClusterSizer project: servers, storage, VMs and
    network at the Primary and DR site, plus all derived metrics needed
    for capacity planning."""

    name: str = "New Project"

    servers: list[Server] = field(default_factory=list)
    storages: list[Storage] = field(default_factory=list)
    vms: list[VirtualMachine] = field(default_factory=list)
    switches: list[NetworkSwitch] = field(default_factory=list)
    connections: list[NetworkConnection] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Filtering by site
    # ------------------------------------------------------------------

    def servers_at(self, site: str) -> list[Server]:
        return [s for s in self.servers if s.site == site]

    def storages_at(self, site: str) -> list[Storage]:
        return [s for s in self.storages if s.site == site]

    def vms_at(self, site: str) -> list[VirtualMachine]:
        return [v for v in self.vms if v.site == site]

    def switches_at(self, site: str) -> list[NetworkSwitch]:
        return [s for s in self.switches if s.site == site]

    # ------------------------------------------------------------------
    # Totals (whole project, both sites)
    # ------------------------------------------------------------------

    @property
    def server_count(self) -> int:
        return len(self.servers)

    @property
    def total_ram(self) -> int:
        return sum(server.ram_gb for server in self.servers)

    @property
    def total_cores(self) -> int:
        return sum(server.total_cores for server in self.servers)

    @property
    def total_threads(self) -> int:
        return sum(server.total_threads for server in self.servers)

    # ------------------------------------------------------------------
    # Physical capacity by site
    # ------------------------------------------------------------------

    def physical_cores(self, site: str) -> int:
        return sum(s.total_cores for s in self.servers_at(site))

    def physical_threads(self, site: str) -> int:
        return sum(s.total_threads for s in self.servers_at(site))

    def physical_ram_gb(self, site: str) -> float:
        return sum(s.ram_gb for s in self.servers_at(site))

    def usable_storage_gb(self, site: str) -> float:
        return sum(s.usable_capacity_gb for s in self.storages_at(site))

    # ------------------------------------------------------------------
    # Demand (VMs) by site - "what's actually running here today"
    # ------------------------------------------------------------------
    # CPU and RAM are only consumed by a VM while it's actually powered
    # on - a powered-off VM releases its CPU/RAM back to the hypervisor.
    # Disk is NOT filtered by power state: a powered-off VM's disk files
    # still sit on the datastore taking up space, so storage demand
    # includes it regardless.
    # ------------------------------------------------------------------

    def vm_vcpu_demand(self, site: str) -> int:
        return sum(v.vcpu for v in self.vms_at(site) if v.powered_on)

    def vm_ram_demand_gb(self, site: str) -> float:
        return sum(v.ram_gb for v in self.vms_at(site) if v.powered_on)

    def vm_disk_demand_gb(self, site: str) -> float:
        return sum(v.disk_gb for v in self.vms_at(site))

    # ------------------------------------------------------------------
    # Oversubscription (demand / physical capacity), by site
    # ------------------------------------------------------------------

    def cpu_oversubscription_ratio(self, site: str) -> float | None:
        """vCPU : physical core. None if there are no physical cores (division by 0)."""
        cores = self.physical_cores(site)
        if cores == 0:
            return None
        return self.vm_vcpu_demand(site) / cores

    def ram_oversubscription_ratio(self, site: str) -> float | None:
        ram = self.physical_ram_gb(site)
        if ram == 0:
            return None
        return self.vm_ram_demand_gb(site) / ram

    def storage_utilization_ratio(self, site: str) -> float | None:
        usable = self.usable_storage_gb(site)
        if usable == 0:
            return None
        return self.vm_disk_demand_gb(site) / usable

    # ------------------------------------------------------------------
    # N+1 check (does the cluster survive losing one host at this site)
    # ------------------------------------------------------------------

    def n_plus_one_ok(self, site: str) -> bool | None:
        """True if the cluster at this site still has enough RAM and cores
        for all VMs if the single (largest) host went down. None if there
        are no servers at this site."""
        site_servers = self.servers_at(site)
        if not site_servers:
            return None

        largest = max(site_servers, key=lambda s: s.ram_gb)
        remaining_ram = self.physical_ram_gb(site) - largest.ram_gb
        remaining_cores = self.physical_cores(site) - largest.total_cores

        ram_ok = remaining_ram >= self.vm_ram_demand_gb(site)
        cpu_ok = remaining_cores >= self.vm_vcpu_demand(site)

        return ram_ok and cpu_ok

    # ------------------------------------------------------------------
    # DR failover demand - "what DR would have to carry if the Primary
    # site went down completely". This is NOT the same as vm_vcpu_demand(DR):
    # that's VMs already running on DR today, while this is VMs that would
    # NEWLY arrive on DR (only the ones with dr_protected=True), at their
    # DR footprint (which may be smaller than the Primary footprint), PLUS
    # whatever is already physically running on DR.
    #
    # CPU/RAM only count PRIMARY VMs that are dr_protected AND currently
    # powered on (a powered-off VM isn't consuming CPU/RAM anywhere right
    # now, so it wouldn't need reserving on DR either). Disk is NOT
    # filtered by power state, same reasoning as vm_disk_demand_gb: a
    # replicated disk still occupies space on the DR target even while
    # the source VM is powered off.
    # ------------------------------------------------------------------

    def dr_failover_vcpu_demand(self) -> int:
        protected = sum(
            v.effective_dr_vcpu for v in self.vms_at(PRIMARY)
            if v.dr_protected and v.powered_on
        )
        return protected + self.vm_vcpu_demand(DR)

    def dr_failover_ram_demand_gb(self) -> float:
        protected = sum(
            v.effective_dr_ram_gb for v in self.vms_at(PRIMARY)
            if v.dr_protected and v.powered_on
        )
        return protected + self.vm_ram_demand_gb(DR)

    def dr_failover_disk_demand_gb(self) -> float:
        protected = sum(
            v.effective_dr_disk_gb for v in self.vms_at(PRIMARY) if v.dr_protected
        )
        return protected + self.vm_disk_demand_gb(DR)

    def dr_protected_vm_count(self) -> int:
        return sum(1 for v in self.vms_at(PRIMARY) if v.dr_protected)

    # ------------------------------------------------------------------
    # DR readiness: can the DR site take on all dr_protected VMs (at their
    # DR footprint) plus whatever is already running on DR?
    # ------------------------------------------------------------------

    def dr_cpu_ok(self) -> bool | None:
        if not self.servers_at(DR):
            return None
        return self.physical_cores(DR) >= self.dr_failover_vcpu_demand()

    def dr_ram_ok(self) -> bool | None:
        if not self.servers_at(DR):
            return None
        return self.physical_ram_gb(DR) >= self.dr_failover_ram_demand_gb()

    def dr_storage_ok(self) -> bool | None:
        if not self.storages_at(DR):
            return None
        return self.usable_storage_gb(DR) >= self.dr_failover_disk_demand_gb()

    def dr_ready(self) -> bool | None:
        """None if the DR site has no resources defined at all (no point
        evaluating readiness)."""
        checks = [self.dr_cpu_ok(), self.dr_ram_ok(), self.dr_storage_ok()]
        if all(c is None for c in checks):
            return None
        return all(c is not False for c in checks)
