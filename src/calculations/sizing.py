"""Pure calculation logic for capacity planning - no dependency on the GUI,
so it can be tested and reused from Reports/CLI if ever needed."""

from dataclasses import dataclass

from src.models.cluster_project import ClusterProject, PRIMARY, DR
from .thresholds import Thresholds, Status


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

    n_plus_one_ok: bool | None
    ht_state: str  # "all_on" | "all_off" | "mixed" | "no_servers"


@dataclass
class DRReport:
    cpu_ok: bool | None
    ram_ok: bool | None
    storage_ok: bool | None
    ready: bool | None

    protected_vm_count: int
    failover_vcpu_demand: int
    failover_ram_demand_gb: float
    failover_disk_demand_gb: float


def build_site_report(project: ClusterProject, site: str, thresholds: Thresholds) -> SiteReport:
    cpu_ratio = project.cpu_oversubscription_ratio(site)
    ram_ratio = project.ram_oversubscription_ratio(site)
    storage_ratio = project.storage_utilization_ratio(site)

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
        n_plus_one_ok=project.n_plus_one_ok(site),
        ht_state=project.hyperthreading_state(site),
    )


def build_dr_report(project: ClusterProject) -> DRReport:
    return DRReport(
        cpu_ok=project.dr_cpu_ok(),
        ram_ok=project.dr_ram_ok(),
        storage_ok=project.dr_storage_ok(),
        ready=project.dr_ready(),
        protected_vm_count=project.dr_protected_vm_count(),
        failover_vcpu_demand=project.dr_failover_vcpu_demand(),
        failover_ram_demand_gb=project.dr_failover_ram_demand_gb(),
        failover_disk_demand_gb=project.dr_failover_disk_demand_gb(),
    )


def build_reports(
    project: ClusterProject, thresholds: Thresholds
) -> tuple[SiteReport, SiteReport, DRReport]:
    primary = build_site_report(project, PRIMARY, thresholds)
    dr = build_site_report(project, DR, thresholds)
    dr_report = build_dr_report(project)
    return primary, dr, dr_report
