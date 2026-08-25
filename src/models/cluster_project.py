from dataclasses import dataclass, field

from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem

PRIMARY = "Primary"
DR = "DR"


@dataclass
class NPlusOneCheck:
    """Detail behind n_plus_one_ok() - which resource (if any) would run
    short after losing the largest host, and by how much, so the UI can
    say something more useful than a bare Yes/No."""
    ram_ok: bool
    cpu_ok: bool
    ram_shortfall_gb: float  # 0 if ram_ok
    cpu_shortfall_effective_cores: float  # 0 if cpu_ok - additional effective cores needed

    @property
    def ok(self) -> bool:
        return self.ram_ok and self.cpu_ok


@dataclass
class HyperthreadingSummary:
    """Detail behind hyperthreading_state() - the classification plus the
    counts behind it, so a caller like ServersPage's global HT toggle can
    show "(3/8 have HT on)" without recomputing the same thing inline."""
    state: str  # "all_on" | "all_off" | "mixed" | "no_servers"
    on_count: int
    total_count: int


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
    backup_destinations: list[BackupDestination] = field(default_factory=list)
    maintenance_items: list[MaintenanceItem] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Filtering by site
    # ------------------------------------------------------------------

    def servers_at(self, site: str) -> list[Server]:
        """Only ENABLED servers - a disabled server is excluded from all
        capacity math (this is the one place that filtering happens; every
        capacity calculation goes through here) while staying visible in
        the Servers table for re-enabling later."""
        return [s for s in self.servers if s.site == site and s.enabled]

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
        return len([s for s in self.servers if s.enabled])

    @property
    def total_ram(self) -> int:
        return sum(server.ram_gb for server in self.servers if server.enabled)

    @property
    def total_cores(self) -> int:
        return sum(server.total_cores for server in self.servers if server.enabled)

    @property
    def total_threads(self) -> int:
        return sum(server.total_threads for server in self.servers if server.enabled)

    @property
    def total_effective_cores(self) -> int:
        """HT-aware, unlike total_threads - respects each server's OWN
        hyperthreading_enabled toggle (total_threads counts full SMT
        width for every server regardless of whether HT is actually on
        for it). This is what's actually available for CPU capacity
        planning - same effective_cores logic physical_cores(site) uses,
        just summed across both sites for the dashboard card. Disabled
        servers are excluded, same as everywhere else."""
        return sum(server.effective_cores for server in self.servers if server.enabled)

    # ------------------------------------------------------------------
    # Physical capacity by site
    # ------------------------------------------------------------------

    def physical_cores(self, site: str) -> int:
        """CPU capacity used for oversubscription math. This is
        HT-adjusted PER SERVER: a server with hyperthreading_enabled=True
        contributes its threads (cores * threads_per_core), one with it
        disabled contributes just its physical cores - see
        Server.effective_cores. Not a straight sum of `sockets *
        cores_per_socket` across all servers."""
        return sum(s.effective_cores for s in self.servers_at(site))

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
    # Hyperthreading state summary - "all_on" / "all_off" / "mixed" /
    # "no_servers". Used to show an HT indicator on Summary/Reports/
    # Compare, since it changes what the HT-adjusted core count means.
    # ------------------------------------------------------------------

    def hyperthreading_summary(self, site: str | None = None) -> "HyperthreadingSummary":
        """Same classification as hyperthreading_state(), but also
        exposes the counts behind it (on_count/total_count) - what
        ServersPage's global HT toggle needs for its "(3/8 have HT on)"
        label, which a bare state string can't carry. site=None means
        ALL servers project-wide (what the Servers tab's toolbar toggle
        applies to); pass a specific site for the per-site Summary/
        Reports/Compare display."""
        servers = self.servers if site is None else self.servers_at(site)
        if not servers:
            return HyperthreadingSummary(state="no_servers", on_count=0, total_count=0)

        on_count = sum(1 for s in servers if s.hyperthreading_enabled)
        total_count = len(servers)
        if on_count == total_count:
            state = "all_on"
        elif on_count == 0:
            state = "all_off"
        else:
            state = "mixed"
        return HyperthreadingSummary(state=state, on_count=on_count, total_count=total_count)

    def hyperthreading_state(self, site: str) -> str:
        return self.hyperthreading_summary(site).state

    # ------------------------------------------------------------------

    def n_plus_one_check(self, site: str, cpu_warning_ratio: float = 1.0) -> "NPlusOneCheck | None":
        """Same math as n_plus_one_ok(), but reports WHICH resource (if
        any) falls short after losing the largest host, and by how much -
        so the UI can say something more useful than a bare Yes/No, e.g.
        "would survive with +150GB RAM". None if there are no servers at
        this site. See n_plus_one_ok()'s docstring for the RAM-strict/
        CPU-tolerant reasoning."""
        site_servers = self.servers_at(site)
        if not site_servers:
            return None

        largest_ram_host = max(site_servers, key=lambda s: s.ram_gb)
        largest_core_host = max(site_servers, key=lambda s: s.effective_cores)

        remaining_ram = self.physical_ram_gb(site) - largest_ram_host.ram_gb
        remaining_cores = self.physical_cores(site) - largest_core_host.effective_cores

        ram_demand = self.vm_ram_demand_gb(site)
        vcpu_demand = self.vm_vcpu_demand(site)
        required_effective_cores = vcpu_demand / cpu_warning_ratio if cpu_warning_ratio > 0 else vcpu_demand

        ram_ok = remaining_ram >= ram_demand
        cpu_ok = remaining_cores >= required_effective_cores

        return NPlusOneCheck(
            ram_ok=ram_ok,
            cpu_ok=cpu_ok,
            ram_shortfall_gb=max(0.0, ram_demand - remaining_ram),
            cpu_shortfall_effective_cores=max(0.0, required_effective_cores - remaining_cores),
        )

    def n_plus_one_ok(self, site: str, cpu_warning_ratio: float = 1.0) -> bool | None:
        """True if the cluster at this site still has enough RAM AND
        enough CPU no matter WHICH single host goes down - RAM headroom
        is checked against the RAM-largest host, CPU headroom against the
        cores-largest host, independently (they are not always the same
        host). None if there are no servers at this site.

        RAM is checked with ZERO oversubscription tolerance (remaining
        RAM must literally cover remaining demand) - RAM overcommit
        causes swapping/ballooning, a fundamentally different and worse
        risk than CPU time-slicing. CPU is checked against
        cpu_warning_ratio (defaults to a strict 1.0 = no tolerance if not
        given) - a healthy cluster is EXPECTED to run some CPU
        oversubscription day to day, so "survives losing a host" should
        mean "stays within your configured comfort threshold after the
        loss", not "reaches literal 1:1 vCPU:pCPU". Pass your project's
        Thresholds.cpu_warning_ratio here for a realistic answer -
        build_site_report() already does. Use n_plus_one_check() instead
        of this if you need to know WHICH resource is short, not just
        whether the whole thing passes."""
        check = self.n_plus_one_check(site, cpu_warning_ratio)
        return check.ok if check is not None else None

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
