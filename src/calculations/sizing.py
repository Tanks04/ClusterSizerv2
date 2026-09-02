"""Pure calculation logic for capacity planning - no dependency on the GUI,
so it can be tested and reused from Reports/CLI if ever needed."""

from dataclasses import dataclass

from src.models.cluster_project import ClusterProject, NPlusOneCheck, PRIMARY, DR
from src.calculations.thresholds import Thresholds, Status, effective_cpu_status


@dataclass
class SiteReport:
    site: str

    server_count: int
    physical_cores: int
    physical_threads: int
    physical_ram_gb: float
    usable_storage_gb: float

    vm_count: int
    vcpu_demand: int
    ram_demand_gb: float
    disk_demand_gb: float

    cpu_ratio: float | None
    ram_ratio: float | None
    storage_ratio: float | None

    cpu_status: Status
    ram_status: Status
    storage_status: Status

    # Tier-weighted "effective" CPU ratio - see HOW_THE_MATH_WORKS.md
    # \u00a72a. Separate from cpu_ratio/cpu_status above: this treats
    # each VM's vCPU as vcpu/tier_ratio rather than counting every
    # vCPU the same, and uses fixed (not Settings-adjustable) cutoffs.
    effective_cpu_ratio: float | None
    effective_cpu_status: Status

    n_plus_one_ok: bool | None
    n_plus_one_check: NPlusOneCheck | None  # detail - which resource is short, by how much
    ht_state: str  # "all_on" | "all_off" | "mixed" | "no_servers"


@dataclass
class FailoverReport:
    cpu_ok: bool | None
    ram_ok: bool | None
    storage_ok: bool | None
    ready: bool | None

    assigned_vm_count: int
    failover_vcpu_demand: int
    failover_ram_demand_gb: float
    failover_disk_demand_gb: float


def build_site_report(project: ClusterProject, site: str, thresholds: Thresholds) -> SiteReport:
    cpu_ratio = project.cpu_oversubscription_ratio(site)
    ram_ratio = project.ram_oversubscription_ratio(site)
    storage_ratio = project.storage_utilization_ratio(site)
    effective_ratio = project.effective_cpu_ratio(site)
    n1_check = project.n_plus_one_check(site, thresholds.cpu_warning_ratio)

    return SiteReport(
        site=site,
        server_count=len(project.servers_at(site)),
        physical_cores=project.physical_cores(site),
        physical_threads=project.physical_threads(site),
        physical_ram_gb=project.physical_ram_gb(site),
        usable_storage_gb=project.usable_storage_gb(site),
        vm_count=len(project.vms_at(site)),
        vcpu_demand=project.vm_vcpu_demand(site),
        ram_demand_gb=project.vm_ram_demand_gb(site),
        disk_demand_gb=project.vm_disk_demand_gb(site),
        cpu_ratio=cpu_ratio,
        ram_ratio=ram_ratio,
        storage_ratio=storage_ratio,
        cpu_status=thresholds.cpu_status(cpu_ratio),
        ram_status=thresholds.ram_status(ram_ratio),
        storage_status=thresholds.storage_status(storage_ratio),
        effective_cpu_ratio=effective_ratio,
        effective_cpu_status=effective_cpu_status(effective_ratio),
        n_plus_one_ok=n1_check.ok if n1_check is not None else None,
        n_plus_one_check=n1_check,
        ht_state=project.hyperthreading_state(site),
    )


def build_failover_report(project: ClusterProject, site: str, thresholds: Thresholds) -> FailoverReport:
    """Generic per-site version - works for any site in project.site_names,
    not just a fixed "DR"."""
    return FailoverReport(
        cpu_ok=project.failover_cpu_ok(site, thresholds),
        ram_ok=project.failover_ram_ok(site),
        storage_ok=project.failover_storage_ok(site),
        ready=project.failover_ready(site, thresholds),
        assigned_vm_count=project.failover_assigned_vm_count(site),
        failover_vcpu_demand=project.failover_vcpu_demand(site),
        failover_ram_demand_gb=project.failover_ram_demand_gb(site),
        failover_disk_demand_gb=project.failover_disk_demand_gb(site),
    )


def build_failover_scenario_report(project: ClusterProject, site: str, thresholds: Thresholds) -> SiteReport:
    """Same shape as build_site_report(site), but demand is the FAILOVER
    scenario - this site's own baseline VMs PLUS every VM assigned to
    fail over here (project.failover_*_demand(), which already combines
    both) - "what would this site need to carry if its failover
    assignments were activated right now", not what's actually running
    there today. Physical capacity (servers/cores/RAM/storage) is this
    site's real hardware, unchanged - only the demand side of each
    ratio flips to the failover scenario, reusing the exact same OK/
    Warning/Critical status system as every other capacity check in the
    app, so "would this site survive activating its failover plan"
    reads the same way "is this site healthy today" already does."""
    vcpu_demand = project.failover_vcpu_demand(site)
    ram_demand_gb = project.failover_ram_demand_gb(site)
    disk_demand_gb = project.failover_disk_demand_gb(site)

    physical_cores = project.physical_cores(site)
    physical_ram_gb = project.physical_ram_gb(site)
    usable_storage_gb = project.usable_storage_gb(site)

    cpu_ratio = (vcpu_demand / physical_cores) if physical_cores > 0 else None
    ram_ratio = (ram_demand_gb / physical_ram_gb) if physical_ram_gb > 0 else None
    storage_ratio = (disk_demand_gb / usable_storage_gb) if usable_storage_gb > 0 else None
    effective_vcpu_demand = project.effective_failover_vcpu_demand(site)
    effective_ratio = (effective_vcpu_demand / physical_cores) if physical_cores > 0 else None

    n1_check = project.n_plus_one_check(site, thresholds.cpu_warning_ratio)

    return SiteReport(
        site=site,
        server_count=len(project.servers_at(site)),
        physical_cores=physical_cores,
        physical_threads=project.physical_threads(site),
        physical_ram_gb=physical_ram_gb,
        usable_storage_gb=usable_storage_gb,
        vm_count=project.failover_assigned_vm_count(site) + len(project.vms_at(site)),
        vcpu_demand=vcpu_demand,
        ram_demand_gb=ram_demand_gb,
        disk_demand_gb=disk_demand_gb,
        cpu_ratio=cpu_ratio,
        ram_ratio=ram_ratio,
        storage_ratio=storage_ratio,
        cpu_status=thresholds.cpu_status(cpu_ratio),
        ram_status=thresholds.ram_status(ram_ratio),
        storage_status=thresholds.storage_status(storage_ratio),
        effective_cpu_ratio=effective_ratio,
        effective_cpu_status=effective_cpu_status(effective_ratio),
        n_plus_one_ok=n1_check.ok if n1_check is not None else None,
        n_plus_one_check=n1_check,
        ht_state=project.hyperthreading_state(site),
    )


def build_reports(project: ClusterProject, thresholds: Thresholds) -> dict[str, SiteReport]:
    """One SiteReport per site in project.site_names - was a fixed
    (primary, dr, dr_report) 3-tuple before N-site support; callers now
    look up whichever sites they need by name."""
    return {site: build_site_report(project, site, thresholds) for site in project.site_names}
