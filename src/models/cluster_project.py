from dataclasses import dataclass, field

from src.calculations.thresholds import Thresholds, Status
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.vlan import Vlan
from src.models.cluster import Cluster
from src.models.failover_assignment import FailoverAssignment

PRIMARY = "Primary"
DR = "DR"

DEPLOYMENT_MODELS = ["On-Premise", "Cloud"]
ON_PREMISE = "On-Premise"
CLOUD = "Cloud"


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

    # The actual list of sites this project tracks - starts as the
    # familiar Primary/DR pair so every existing project loads
    # completely unchanged, but isn't limited to exactly two. PRIMARY
    # is always assumed present throughout the app (it's the "main"
    # site everything else is sized against) - see remove_site().
    site_names: list[str] = field(default_factory=lambda: [PRIMARY, DR])

    # Per-site settings, keyed by site name - a dict instead of two
    # hardcoded fields (the earlier primary_X/dr_X shape) specifically
    # so this scales to however many sites are in site_names. A site
    # with no entry here defaults to On-Premise / 0 (not entered) -
    # same effective defaults as before this was a dict.
    site_deployment_models: dict[str, str] = field(default_factory=dict)
    site_rack_capacity_u: dict[str, int] = field(default_factory=dict)

    servers: list[Server] = field(default_factory=list)
    storages: list[Storage] = field(default_factory=list)
    vms: list[VirtualMachine] = field(default_factory=list)
    switches: list[NetworkSwitch] = field(default_factory=list)
    connections: list[NetworkConnection] = field(default_factory=list)
    backup_destinations: list[BackupDestination] = field(default_factory=list)
    maintenance_items: list[MaintenanceItem] = field(default_factory=list)
    vlans: list[Vlan] = field(default_factory=list)
    clusters: list[Cluster] = field(default_factory=list)

    # Per-project overrides of WORKLOAD_TIERS' catalog default_ratio -
    # e.g. {"Tier-0 / Mission-Critical": 1.5} to use 1.5 instead of the
    # catalog's 1.0 for THIS project only. Empty by default (catalog
    # values apply everywhere). Edited on the Settings tab.
    tier_ratio_overrides: dict[str, float] = field(default_factory=dict)
    failover_assignments: list[FailoverAssignment] = field(default_factory=list)

    def add_site(self, name: str) -> None:
        name = name.strip()
        if name and name not in self.site_names:
            self.site_names.append(name)

    def remove_site(self, name: str) -> None:
        """Removing PRIMARY is refused outright - too much of the rest
        of the app (capacity math, reports, the Summary layout) assumes
        it always exists as "the main site" to size everything against.
        Whether entities still reference `name` is a ProjectService-level
        concern (same policy as VLAN deletion elsewhere), not this
        model method's - this just removes it from the list and its
        own per-site settings."""
        if name == PRIMARY:
            raise ValueError("Cannot remove the Primary site")
        self.site_names = [s for s in self.site_names if s != name]
        self.site_deployment_models.pop(name, None)
        self.site_rack_capacity_u.pop(name, None)

    def deployment_model_for(self, site: str) -> str:
        return self.site_deployment_models.get(site, ON_PREMISE)

    def set_deployment_model(self, site: str, model: str) -> None:
        self.site_deployment_models[site] = model

    def is_cloud(self, site: str) -> bool:
        return self.deployment_model_for(site) == CLOUD

    def rack_capacity_u_for(self, site: str) -> int:
        return self.site_rack_capacity_u.get(site, 0)

    def set_rack_capacity_u(self, site: str, capacity: int) -> None:
        self.site_rack_capacity_u[site] = capacity

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

    def tier_ratio_for_project(self, tier_name: str) -> float:
        """Same as workload_tier.tier_ratio_for(), but checks this
        project's own tier_ratio_overrides first - lets someone dial
        in their own oversubscription-tolerance assumptions per
        project instead of always using the shared catalog defaults."""
        from src.models.workload_tier import tier_ratio_for
        if tier_name in self.tier_ratio_overrides:
            return self.tier_ratio_overrides[tier_name]
        return tier_ratio_for(tier_name)

    def effective_vcpu_demand(self, site: str) -> float:
        """Same idea as vm_vcpu_demand, but each VM's vCPU is scaled by
        its Workload Tier's oversubscription tolerance first (vm.vcpu /
        tier_ratio) - the same formula Cluster Preparation already uses
        to decide how many hosts to buy, reused here so an EXISTING
        cluster's tier mix is reflected the same way. A Tier-0 VM
        (ratio 1.0) counts at full weight; a VDI VM (ratio 12.0) counts
        at a small fraction of it, since it tolerates far more
        contention in practice."""
        return sum(
            v.vcpu / self.tier_ratio_for_project(v.workload_tier)
            for v in self.vms_at(site) if v.powered_on
        )

    def effective_cpu_ratio(self, site: str) -> float | None:
        """Effective vCPU : physical core - unlike the raw ratio above,
        1.0 here means "fully booked assuming zero oversubscription
        tolerance anywhere", since Tier-0's own ratio is 1.0 and every
        other tier only reduces its contribution. None if there are no
        physical cores."""
        cores = self.physical_cores(site)
        if cores == 0:
            return None
        return self.effective_vcpu_demand(site) / cores

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
    # Per-pool storage utilization - opt-in, only meaningful once a VM
    # is actually assigned to a SPECIFIC Storage entity (VirtualMachine.
    # storage_uid). The site-wide totals above are UNCHANGED and stay
    # the headline number regardless of whether any VM uses this - it's
    # possible for the site aggregate to look perfectly healthy while
    # one specific pool is dangerously full and another sits empty,
    # which the aggregate alone can never reveal.
    # ------------------------------------------------------------------

    def storage_pool_demand_gb(self, storage_uid: str) -> float:
        return sum(
            vm.disk_gb for vm in self.vms
            if vm.storage_uid == storage_uid
        )

    def storage_pool_utilization_ratio(self, storage: Storage) -> float | None:
        usable_gb = storage.usable_capacity_tb * 1024
        if usable_gb == 0:
            return None
        return self.storage_pool_demand_gb(storage.uid) / usable_gb

    # ------------------------------------------------------------------
    # Per-cluster CPU/RAM utilization - opt-in, only meaningful once a
    # Server/VM is actually assigned to a SPECIFIC Cluster (both have
    # a cluster_uid). Exactly the same "aggregate can hide a real
    # problem" pattern as storage pools above: a site's overall CPU/RAM
    # can look perfectly healthy while one specific isolated cluster
    # (a vSphere Cluster, a Nutanix cluster, one of several independent
    # Hyper-V clusters at the same site) is over-subscribed - the site
    # aggregate alone can never reveal that.
    # ------------------------------------------------------------------

    def cluster_physical_cores(self, cluster_uid: str) -> int:
        return sum(s.effective_cores for s in self.servers if s.cluster_uid == cluster_uid)

    def cluster_physical_ram_gb(self, cluster_uid: str) -> float:
        return sum(s.ram_gb for s in self.servers if s.cluster_uid == cluster_uid)

    def cluster_vcpu_demand(self, cluster_uid: str) -> int:
        return sum(v.vcpu for v in self.vms if v.cluster_uid == cluster_uid and v.powered_on)

    def cluster_ram_demand_gb(self, cluster_uid: str) -> float:
        return sum(v.ram_gb for v in self.vms if v.cluster_uid == cluster_uid and v.powered_on)

    def cluster_cpu_ratio(self, cluster_uid: str) -> float | None:
        cores = self.cluster_physical_cores(cluster_uid)
        if cores == 0:
            return None
        return self.cluster_vcpu_demand(cluster_uid) / cores

    def cluster_ram_ratio(self, cluster_uid: str) -> float | None:
        ram = self.cluster_physical_ram_gb(cluster_uid)
        if ram == 0:
            return None
        return self.cluster_ram_demand_gb(cluster_uid) / ram

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
    # Failover demand - "what site X would have to carry if it started
    # receiving its assigned failover VMs on top of what it already
    # runs". Generalized across any number of sites via
    # FailoverAssignment (not just a fixed Primary->DR relationship) -
    # each assignment is one VM's footprint on ONE target site, since
    # the same VM can need a different footprint on different targets
    # (e.g. smaller on a budget DR site than a full second DR).
    #
    # CPU/RAM only count an assignment if its VM is currently powered
    # on (a powered-off VM isn't consuming CPU/RAM anywhere right now,
    # so it wouldn't need reserving on a failover target either). Disk
    # is NOT filtered by power state, same reasoning as
    # vm_disk_demand_gb: replicated disk still occupies space on the
    # target even while the source VM is powered off.
    # ------------------------------------------------------------------

    def failover_assignments_for(self, site: str) -> list["FailoverAssignment"]:
        """Assignments targeting this site - excludes any whose VM
        already physically lives AT this site (not a "failover" if
        it's already there) or whose VM no longer exists (orphaned;
        ProjectService cleans these up when a VM is deleted, but this
        stays defensive regardless)."""
        vm_by_uid = {v.uid: v for v in self.vms}
        result = []
        for a in self.failover_assignments:
            if a.target_site != site:
                continue
            vm = vm_by_uid.get(a.vm_uid)
            if vm is None or vm.site == site:
                continue
            result.append(a)
        return result

    def failover_vcpu_demand(self, site: str) -> int:
        vm_by_uid = {v.uid: v for v in self.vms}
        total = self.vm_vcpu_demand(site)
        for a in self.failover_assignments_for(site):
            if vm_by_uid[a.vm_uid].powered_on:
                total += a.vcpu
        return total

    def effective_failover_vcpu_demand(self, site: str) -> float:
        """Same idea as failover_vcpu_demand, but each contribution is
        scaled by the VM's own Workload Tier tolerance first, matching
        effective_vcpu_demand above - so "would this site's failover
        plan hold up" accounts for tier mix the same way "is this site
        healthy today" does."""
        vm_by_uid = {v.uid: v for v in self.vms}
        total = self.effective_vcpu_demand(site)
        for a in self.failover_assignments_for(site):
            vm = vm_by_uid[a.vm_uid]
            if vm.powered_on:
                total += a.vcpu / self.tier_ratio_for_project(vm.workload_tier)
        return total

    def failover_ram_demand_gb(self, site: str) -> float:
        vm_by_uid = {v.uid: v for v in self.vms}
        total = self.vm_ram_demand_gb(site)
        for a in self.failover_assignments_for(site):
            if vm_by_uid[a.vm_uid].powered_on:
                total += a.ram_gb
        return total

    def failover_disk_demand_gb(self, site: str) -> float:
        total = self.vm_disk_demand_gb(site)
        for a in self.failover_assignments_for(site):
            total += a.disk_gb
        return total

    def failover_assigned_vm_count(self, site: str) -> int:
        return len(self.failover_assignments_for(site))

    # ------------------------------------------------------------------
    # Failover readiness: can this site take on everything assigned to
    # it (plus whatever it already runs)?
    # ------------------------------------------------------------------

    def failover_cpu_ok(self, site: str, thresholds: Thresholds) -> bool | None:
        """Whether this site's CPU can absorb its own baseline load plus
        assigned failover VMs - uses the SAME oversubscription ratio
        threshold as ordinary CPU status (e.g. 4:1 warning/6:1 critical),
        not a strict physical_cores >= vcpu_demand comparison. That
        stricter check effectively demanded near-1:1 provisioning and
        flagged perfectly healthy, normally-oversubscribed sites (e.g.
        3.75:1, well under a 4:1 warning threshold) as "not enough
        capacity" - a real bug found from a live report."""
        cores = self.physical_cores(site)
        if cores == 0:
            return None
        ratio = self.failover_vcpu_demand(site) / cores
        return thresholds.cpu_status(ratio) != Status.CRITICAL

    def failover_ram_ok(self, site: str) -> bool | None:
        if not self.servers_at(site):
            return None
        return self.physical_ram_gb(site) >= self.failover_ram_demand_gb(site)

    def failover_storage_ok(self, site: str) -> bool | None:
        if not self.storages_at(site):
            return None
        return self.usable_storage_gb(site) >= self.failover_disk_demand_gb(site)

    def failover_ready(self, site: str, thresholds: Thresholds) -> bool | None:
        """None if the site has no resources defined at all (no point
        evaluating readiness)."""
        checks = [self.failover_cpu_ok(site, thresholds), self.failover_ram_ok(site), self.failover_storage_ok(site)]
        if all(c is None for c in checks):
            return None
        return all(c is not False for c in checks)
