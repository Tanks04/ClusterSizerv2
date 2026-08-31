"""Cluster Preparation - reverse-direction sizing: given the VMs you NEED
to run, how many hosts of a given spec should you buy? This is a
DIFFERENT calculation from the app's existing oversubscription-ratio
checks (Summary/VMs/Reports), which answer "given the servers I HAVE, is
my vCPU:pCPU ratio safe". Cluster Preparation uses a per-VM
oversubscription-ratio-tier model instead of a single flat ratio, since
a single project-wide ratio is too blunt when sizing new hardware from
scratch. No Qt dependency, so it's testable on its own.

The host spec (sockets/cores/RAM per host) is an OUTPUT of this module,
not an input you're expected to already know - compute_sizing() searches
a small grid of common configurations and picks the one that needs the
fewest hosts while landing close to a target CPU oversubscription ratio
(derived from the chosen hypervisor's guidance). You can still override
it explicitly (pass your own HostSpec via SizingPolicy.host_spec) if you
already know what you're buying.
"""

import math
from dataclasses import dataclass, field

from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.models.virtual_machine import VirtualMachine, DR_CATEGORIES
from src.models.workload_tier import WORKLOAD_TIERS, DEFAULT_WORKLOAD_TIER

HA_LEVELS = ["None", "Basic HA", "N+1", "N+2"]

# Extra hosts reserved on top of the base capacity requirement. "None"
# and "Basic HA" both size for the FEWEST hosts that fit today's demand
# with zero reserved failover capacity - the difference between them is
# NOT host count, it's whether the HA feature itself is configured:
# "None" means no automatic VM restart on a host failure at all (that
# host's VMs just stay down); "Basic HA" means restart IS automatic
# (vSphere HA / Failover Clustering with no admission control), but the
# survivors take on the full load with no reserved headroom - VMs come
# back up, just badly oversubscribed until you add capacity. Only N+1/
# N+2 explicitly reserve host-level capacity so a failure causes NO
# capacity shortfall at all.
_HA_EXTRA_HOSTS = {"None": 0, "Basic HA": 0, "N+1": 1, "N+2": 2}

# Never recommend fewer than this many hosts once there's at least one
# VM - a single host is never a "cluster" (no maintenance windows, no
# resilience at all), regardless of HA setting.
_MIN_CLUSTER_HOSTS = 2


@dataclass
class HostSpec:
    """A host configuration - either the one you asked for (SizingPolicy.
    host_spec) or the one compute_sizing() optimized for you. Mirrors the
    fields Server already has, so a result can be turned directly into
    real Server rows."""
    sockets: int = 2
    cores_per_socket: int = 16
    threads_per_core: int = 2
    hyperthreading_enabled: bool = True
    ram_gb: float = 512.0

    @property
    def effective_cores(self) -> int:
        cores = self.sockets * self.cores_per_socket
        return cores * self.threads_per_core if self.hyperthreading_enabled else cores


@dataclass
class SizingPolicy:
    ha_level: str = "N+1"
    growth_percent: float = 30.0
    memory_reserve_percent: float = 20.0  # hypervisor/mgmt/HA/growth overhead
    storage_overhead_percent: float = 20.0  # RAID/EC + headroom, mirrors Storage.raid_overhead_percent

    # Physical CPU cores reserved PER HOST for the hypervisor itself,
    # subtracted from each host's raw core count before computing
    # effective capacity - previously this was only a warning NOTE on
    # the Result page ("not reserved above"), never actually applied to
    # the math, which was itself a real gap: RAM gets a %-based reserve
    # (memory_reserve_percent) but CPU had nothing. Defaults to a small,
    # commonly-cited minimum (roughly matching VMware's ESXi overhead
    # guidance in absolute cores rather than a %, since the hypervisor's
    # own footprint is closer to a fixed cost than proportional to host
    # size). Set to 0 to disable entirely, or raise it if you know your
    # actual footprint is bigger.
    hypervisor_cpu_reserve_cores: int = 2

    # Whether the auto-optimized host spec assumes Hyperthreading is on.
    # Defaults True to preserve prior behavior for any caller not using
    # the wizard's own upfront question (which defaults its own checkbox
    # to False - HT gains vary by workload, so starting conservative
    # without relying on it was the direct preference when this was added).
    assume_hyperthreading: bool = True

    # If None, compute_sizing() picks one for you (see module docstring).
    # Set explicitly to override the auto-optimizer with a spec you
    # already know you're buying.
    host_spec: HostSpec | None = None

    # What CPU oversubscription ratio the auto-optimizer aims for -
    # normally derived from the chosen hypervisor's guidance (roughly
    # 3/4 of its warning threshold, landing comfortably below it - e.g.
    # 2.25:1 for a 3:1 VMware warning), not a fixed constant.
    target_cpu_ratio: float = 2.25

    # Per-tier oversubscription ratio assumptions - starts from the
    # catalog defaults (src/models/workload_tier.py) but is editable per
    # project, since these are assumptions, not measurements.
    ratio_overrides: dict[str, float] = field(default_factory=dict)

    def ratio_for(self, tier_name: str) -> float:
        if tier_name in self.ratio_overrides:
            return self.ratio_overrides[tier_name]
        tier = WORKLOAD_TIERS.get(tier_name) or WORKLOAD_TIERS[DEFAULT_WORKLOAD_TIER]
        return tier.default_ratio


@dataclass
class ManualDemand:
    """Aggregate CPU/RAM/disk demand entered directly, for sizing a
    brand-new cluster before any VMs have been loaded/entered yet -
    compute_sizing() normally reads real VM records from the project,
    which doesn't work for a genuinely empty project. One workload tier
    applies to the whole aggregate (there's no per-VM granularity here
    by nature - if you need that, enter real VMs on the VMs tab
    instead and this input is ignored). DR sizing isn't available in
    this mode, since DR footprint comes from FailoverAssignment records
    tied to real VMs, which don't exist yet either."""

    vcpu: int
    ram_gb: float
    disk_gb: float
    workload_tier: str = DEFAULT_WORKLOAD_TIER

    @property
    def has_demand(self) -> bool:
        return self.vcpu > 0 or self.ram_gb > 0 or self.disk_gb > 0


@dataclass
class SizingResult:
    vm_count: int
    dr_site_vm_count: int  # VMs already tagged site=DR - excluded from Primary sizing, shown so "why fewer than I loaded" has an answer
    workload_breakdown: dict[str, int]  # tier name -> VM count
    used_manual_demand: bool  # True if sized from ManualDemand rather than real VM records

    total_vcpu_raw: int
    total_effective_vcpu: float  # workload-weighted, drives CPU sizing
    total_ram_demand_gb: float
    total_ram_with_reserve_gb: float
    total_storage_demand_gb: float
    recommended_storage_usable_tb: float
    recommended_storage_raw_tb: float

    host_spec: HostSpec  # the spec actually used - optimized, unless you overrode it
    host_effective_cores: int
    hosts_for_cpu: int
    hosts_for_ram: int
    binding_constraint: str  # "CPU" | "RAM"
    raw_oversubscription_ratio: float | None  # simple vCPU:pCPU across required_hosts - a
    # familiar sanity-check number alongside the workload-weighted calc above,
    # not a replacement for it. None if required_hosts is 0.

    ha_extra_hosts: int
    required_hosts: int  # base (post-growth) + HA buffer

    dr_vm_count: int
    dr_hosts_for_cpu: int
    dr_hosts_for_ram: int
    dr_binding_constraint: str
    dr_required_hosts: int
    dr_storage_demand_gb: float
    dr_recommended_storage_usable_tb: float
    dr_recommended_storage_raw_tb: float


def _effective_vcpu(vm: VirtualMachine, policy: SizingPolicy) -> float:
    return vm.vcpu / policy.ratio_for(vm.workload_tier)


def _hosts_needed(demand: float, per_host: float) -> int:
    if per_host <= 0:
        return 0
    return math.ceil(demand / per_host)


# ----------------------------------------------------------------------
# Host spec optimizer
# ----------------------------------------------------------------------

_CORE_CANDIDATES = [8, 12, 16, 24, 32, 48, 64]  # cores per socket, 2 sockets assumed
_RAM_CANDIDATES = [64, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048]


def _optimize_host_spec(
    total_vcpu_raw: int,
    total_effective_vcpu: float,
    total_ram_with_reserve_gb: float,
    target_cpu_ratio: float,
    hypervisor_cpu_reserve_cores: int = 0,
    hyperthreading_enabled: bool = True,
) -> HostSpec:
    """Grid search over common host configurations. Picks the one that
    needs the FEWEST hosts first (fewer physical chassis = cheaper -
    hardware and rack/power/cooling costs add up fast), and among
    ties, the one whose resulting raw vCPU:pCPU ratio lands closest to
    target_cpu_ratio - so you're not paying for far more headroom than
    your chosen hypervisor's own guidance calls for."""
    best_spec = None
    best_key = None  # (hosts, |ratio - target|) - lexicographic min

    for cores in _CORE_CANDIDATES:
        for ram in _RAM_CANDIDATES:
            spec = HostSpec(
                sockets=2, cores_per_socket=cores, threads_per_core=2,
                hyperthreading_enabled=hyperthreading_enabled, ram_gb=float(ram),
            )
            reserved = hypervisor_cpu_reserve_cores * spec.threads_per_core
            usable_effective_cores = max(1, spec.effective_cores - reserved)
            hosts_cpu = _hosts_needed(total_effective_vcpu, usable_effective_cores)
            hosts_ram = _hosts_needed(total_ram_with_reserve_gb, spec.ram_gb)
            hosts = max(hosts_cpu, hosts_ram, _MIN_CLUSTER_HOSTS)

            ratio = total_vcpu_raw / (hosts * usable_effective_cores) if usable_effective_cores > 0 else 0
            key = (hosts, abs(ratio - target_cpu_ratio))

            if best_key is None or key < best_key:
                best_key = key
                best_spec = spec

    return best_spec or HostSpec()


def compute_sizing(
    project: ClusterProject, policy: SizingPolicy, manual_demand: ManualDemand | None = None,
) -> SizingResult:
    growth_factor = 1 + (policy.growth_percent / 100)
    reserve_factor = 1 - (policy.memory_reserve_percent / 100)
    if reserve_factor <= 0:
        reserve_factor = 0.01  # guard against a 100%+ reserve making RAM sizing infinite

    primary_vms = project.vms_at(PRIMARY)
    dr_site_vm_count = len(project.vms_at(DR))

    # Real VMs always take priority - manual_demand is only USED when
    # there genuinely aren't any, matching the wizard's own behavior
    # (the manual input fields are hidden once VMs exist).
    using_manual_demand = not primary_vms and manual_demand is not None and manual_demand.has_demand

    if using_manual_demand:
        breakdown = {manual_demand.workload_tier: 1}  # nominal - there's no real per-VM count to show
        total_vcpu_raw = manual_demand.vcpu
        total_effective_vcpu = (manual_demand.vcpu / policy.ratio_for(manual_demand.workload_tier)) * growth_factor
        total_ram_demand_gb = manual_demand.ram_gb
        total_storage_demand_gb = manual_demand.disk_gb * growth_factor
    else:
        breakdown: dict[str, int] = {}
        for vm in primary_vms:
            breakdown[vm.workload_tier] = breakdown.get(vm.workload_tier, 0) + 1

        total_vcpu_raw = sum(vm.vcpu for vm in primary_vms)
        total_effective_vcpu = sum(_effective_vcpu(vm, policy) for vm in primary_vms) * growth_factor
        total_ram_demand_gb = sum(vm.ram_gb for vm in primary_vms)
        total_storage_demand_gb = sum(vm.disk_gb for vm in primary_vms) * growth_factor
    total_ram_with_reserve_gb = (total_ram_demand_gb * growth_factor) / reserve_factor

    storage_overhead_factor = max(0.01, 1 - (policy.storage_overhead_percent / 100))
    recommended_storage_usable_tb = total_storage_demand_gb / 1024
    recommended_storage_raw_tb = recommended_storage_usable_tb / storage_overhead_factor

    if policy.host_spec is not None:
        host_spec = policy.host_spec
    elif primary_vms or using_manual_demand:
        host_spec = _optimize_host_spec(
            total_vcpu_raw, total_effective_vcpu, total_ram_with_reserve_gb,
            policy.target_cpu_ratio, policy.hypervisor_cpu_reserve_cores,
            policy.assume_hyperthreading,
        )
    else:
        host_spec = HostSpec()

    # Hypervisor CPU reserve is set in PHYSICAL cores - when HT is on,
    # that translates to threads_per_core times as many EFFECTIVE
    # (logical) cores, matching how host_spec.effective_cores itself
    # scales physical cores by threads_per_core.
    ht_multiplier = host_spec.threads_per_core if host_spec.hyperthreading_enabled else 1
    reserved_effective_cores = policy.hypervisor_cpu_reserve_cores * ht_multiplier
    host_effective_cores = max(1, host_spec.effective_cores - reserved_effective_cores)
    hosts_for_cpu = _hosts_needed(total_effective_vcpu, host_effective_cores)
    hosts_for_ram = _hosts_needed(total_ram_with_reserve_gb, host_spec.ram_gb)

    base_hosts = max(hosts_for_cpu, hosts_for_ram, _MIN_CLUSTER_HOSTS if (primary_vms or using_manual_demand) else 0)
    binding_constraint = "RAM" if hosts_for_ram >= hosts_for_cpu else "CPU"

    ha_extra = _HA_EXTRA_HOSTS.get(policy.ha_level, 0)
    required_hosts = base_hosts + ha_extra if (primary_vms or using_manual_demand) else 0

    raw_oversubscription_ratio = (
        total_vcpu_raw / (required_hosts * host_effective_cores)
        if required_hosts > 0 and host_effective_cores > 0 else None
    )

    # DR: reuses each VM's own FailoverAssignment targeting DR (editable
    # on the VMs tab's Failover Assignments table) rather than a
    # separate global "DR capacity %" - see the module/VirtualMachine
    # docstrings for why. Uses the SAME host_spec as Primary (consistent
    # hardware), just a different host COUNT. Scoped to DR specifically
    # (not every site) - this wizard sizes one Primary + one DR-like
    # target at a time, same as before N-site support existed.
    dr_assignments = {a.vm_uid: a for a in project.failover_assignments_for(DR)}
    dr_vms = [vm for vm in primary_vms if vm.uid in dr_assignments]
    dr_effective_vcpu = sum(
        dr_assignments[vm.uid].vcpu / policy.ratio_for(vm.workload_tier) for vm in dr_vms
    ) * growth_factor
    dr_ram_with_reserve = (
        sum(dr_assignments[vm.uid].ram_gb for vm in dr_vms) * growth_factor
    ) / reserve_factor

    dr_hosts_for_cpu = _hosts_needed(dr_effective_vcpu, host_effective_cores)
    dr_hosts_for_ram = _hosts_needed(dr_ram_with_reserve, host_spec.ram_gb)
    dr_base_hosts = max(dr_hosts_for_cpu, dr_hosts_for_ram, 1 if dr_vms else 0)
    dr_binding_constraint = "RAM" if dr_hosts_for_ram >= dr_hosts_for_cpu else "CPU"
    dr_required_hosts = dr_base_hosts + ha_extra if dr_vms else 0

    dr_storage_demand_gb = sum(dr_assignments[vm.uid].disk_gb for vm in dr_vms) * growth_factor
    dr_recommended_storage_usable_tb = dr_storage_demand_gb / 1024
    dr_recommended_storage_raw_tb = dr_recommended_storage_usable_tb / storage_overhead_factor

    return SizingResult(
        vm_count=len(primary_vms),
        dr_site_vm_count=dr_site_vm_count,
        workload_breakdown=breakdown,
        used_manual_demand=using_manual_demand,
        total_vcpu_raw=total_vcpu_raw,
        total_effective_vcpu=total_effective_vcpu,
        total_ram_demand_gb=total_ram_demand_gb,
        total_ram_with_reserve_gb=total_ram_with_reserve_gb,
        total_storage_demand_gb=total_storage_demand_gb,
        recommended_storage_usable_tb=recommended_storage_usable_tb,
        recommended_storage_raw_tb=recommended_storage_raw_tb,
        host_spec=host_spec,
        host_effective_cores=host_effective_cores,
        hosts_for_cpu=hosts_for_cpu,
        hosts_for_ram=hosts_for_ram,
        binding_constraint=binding_constraint,
        raw_oversubscription_ratio=raw_oversubscription_ratio,
        ha_extra_hosts=ha_extra,
        required_hosts=required_hosts,
        dr_vm_count=len(dr_vms),
        dr_hosts_for_cpu=dr_hosts_for_cpu,
        dr_hosts_for_ram=dr_hosts_for_ram,
        dr_binding_constraint=dr_binding_constraint,
        dr_required_hosts=dr_required_hosts,
        dr_storage_demand_gb=dr_storage_demand_gb,
        dr_recommended_storage_usable_tb=dr_recommended_storage_usable_tb,
        dr_recommended_storage_raw_tb=dr_recommended_storage_raw_tb,
    )


# ----------------------------------------------------------------------
# N-site recommendations - a NEW, generic path alongside the DR-specific
# fields above (which stay as-is, driven by pre-existing FailoverAssignment
# records - kept for backward compatibility with anyone already using that
# flow). This one works for ANY site (DR, DR2, a third site, etc.) and is
# driven by DR Category selection instead of requiring FailoverAssignment
# records to already exist - "which categories of Primary VM need to be
# able to run at this site" is asked directly, matching how a real DR
# planning conversation actually goes ("everything except DWH and test/
# dev"), rather than requiring the assignments to be set up by hand first.
# ----------------------------------------------------------------------

@dataclass
class SiteRecommendation:
    site: str
    included_categories: list[str]
    vm_count: int
    included_vm_uids: list[str]  # for creating FailoverAssignment records afterward, if the user opts in

    total_vcpu_raw: int
    effective_vcpu: float
    ram_demand_gb: float
    storage_demand_gb: float

    hosts_for_cpu: int
    hosts_for_ram: int
    binding_constraint: str
    required_hosts: int

    recommended_storage_usable_tb: float
    recommended_storage_raw_tb: float


def compute_site_recommendation(
    project: ClusterProject,
    policy: SizingPolicy,
    host_spec: HostSpec,
    target_site: str,
    included_categories: set[str],
) -> SiteRecommendation:
    """Sizes target_site to hold whichever Primary VMs fall into
    included_categories (VirtualMachine.dr_category) - reuses host_spec
    AS GIVEN rather than re-optimizing, so every site the wizard
    recommends uses the SAME hardware spec as Primary (consistent
    purchasing), just a different host count."""
    growth_factor = 1 + (policy.growth_percent / 100)
    reserve_factor = max(0.01, 1 - (policy.memory_reserve_percent / 100))
    storage_overhead_factor = max(0.01, 1 - (policy.storage_overhead_percent / 100))

    primary_vms = project.vms_at(PRIMARY)
    qualifying_vms = [vm for vm in primary_vms if vm.dr_category in included_categories]

    total_vcpu_raw = sum(vm.vcpu for vm in qualifying_vms)
    effective_vcpu = sum(_effective_vcpu(vm, policy) for vm in qualifying_vms) * growth_factor
    ram_demand_gb = sum(vm.ram_gb for vm in qualifying_vms)
    ram_with_reserve_gb = (ram_demand_gb * growth_factor) / reserve_factor
    storage_demand_gb = sum(vm.disk_gb for vm in qualifying_vms) * growth_factor

    ht_multiplier = host_spec.threads_per_core if host_spec.hyperthreading_enabled else 1
    reserved_effective_cores = policy.hypervisor_cpu_reserve_cores * ht_multiplier
    host_effective_cores = max(1, host_spec.effective_cores - reserved_effective_cores)

    hosts_for_cpu = _hosts_needed(effective_vcpu, host_effective_cores)
    hosts_for_ram = _hosts_needed(ram_with_reserve_gb, host_spec.ram_gb)
    binding_constraint = "RAM" if hosts_for_ram >= hosts_for_cpu else "CPU"

    ha_extra = _HA_EXTRA_HOSTS.get(policy.ha_level, 0)
    base_hosts = max(hosts_for_cpu, hosts_for_ram, _MIN_CLUSTER_HOSTS if qualifying_vms else 0)
    required_hosts = base_hosts + ha_extra if qualifying_vms else 0

    recommended_storage_usable_tb = storage_demand_gb / 1024
    recommended_storage_raw_tb = recommended_storage_usable_tb / storage_overhead_factor

    return SiteRecommendation(
        site=target_site,
        included_categories=sorted(included_categories),
        vm_count=len(qualifying_vms),
        included_vm_uids=[vm.uid for vm in qualifying_vms],
        total_vcpu_raw=total_vcpu_raw,
        effective_vcpu=effective_vcpu,
        ram_demand_gb=ram_demand_gb,
        storage_demand_gb=storage_demand_gb,
        hosts_for_cpu=hosts_for_cpu,
        hosts_for_ram=hosts_for_ram,
        binding_constraint=binding_constraint,
        required_hosts=required_hosts,
        recommended_storage_usable_tb=recommended_storage_usable_tb,
        recommended_storage_raw_tb=recommended_storage_raw_tb,
    )
