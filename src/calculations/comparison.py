"""Pure logic for the Compare Scenarios page - builds a side-by-side
metrics table for two ClusterProjects under the same Thresholds. No Qt
dependency, so it's testable on its own."""

from dataclasses import asdict

from src.calculations.sizing import build_failover_report, build_reports
from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject


def _without_uid(entity) -> dict:
    data = asdict(entity)
    data.pop("uid", None)
    return data


def projects_are_identical(a: ClusterProject, b: ClusterProject) -> bool:
    """True if every entity list matches on VALUE fields (everything
    except `uid`, which is a random per-instance identifier and would
    make two independently-built-but-equivalent projects compare as
    different otherwise). This is the situation you get right after
    'Save Scenario Copy As' if you haven't changed anything since. Used
    by the Compare page to explain a same-looking comparison instead of
    leaving it looking like a bug.

    `project.name` deliberately does NOT participate - two scenarios that
    differ only by name still have identical contents, which is the
    thing this function is answering. Comparison is order-sensitive
    (list position matters, matching dataclass list equality) - this is
    fine for the "did I just re-save the same data" case this exists
    for, but two projects with the same rows in a different order will
    compare as different."""
    return (
        [_without_uid(x) for x in a.servers] == [_without_uid(x) for x in b.servers]
        and [_without_uid(x) for x in a.storages] == [_without_uid(x) for x in b.storages]
        and [_without_uid(x) for x in a.vms] == [_without_uid(x) for x in b.vms]
        and [_without_uid(x) for x in a.switches] == [_without_uid(x) for x in b.switches]
        and [_without_uid(x) for x in a.connections] == [_without_uid(x) for x in b.connections]
    )


def build_delta_summary(project_a: ClusterProject, project_b: ClusterProject) -> list[tuple[str, str]]:
    """Headline deltas (B minus A) for the quick-glance card row at the
    bottom of the Compare page - the "what actually changed" summary,
    separate from the full row-by-row table above it."""

    def delta(value_a, value_b, fmt="{:+d}"):
        d = value_b - value_a
        return fmt.format(d) if d != 0 else "no change"

    servers_a, servers_b = project_a.server_count, project_b.server_count
    cores_a, cores_b = project_a.total_cores, project_b.total_cores
    ram_a, ram_b = project_a.total_ram, project_b.total_ram
    vms_a, vms_b = len(project_a.vms), len(project_b.vms)

    # Every other delta above sums across the whole project already
    # (server_count/total_cores/total_ram are project-wide properties) -
    # storage was the one card still only adding Primary+DR, missing
    # DR2/DR3/any additional site on a 3+-site project.
    storage_a = sum(project_a.usable_storage_gb(site) for site in project_a.site_names) / 1024
    storage_b = sum(project_b.usable_storage_gb(site) for site in project_b.site_names) / 1024

    return [
        ("\u0394 Servers", delta(servers_a, servers_b)),
        ("\u0394 Cores", delta(cores_a, cores_b)),
        ("\u0394 RAM (GB)", delta(ram_a, ram_b)),
        ("\u0394 VMs", delta(vms_a, vms_b)),
        ("\u0394 Storage (TB)", delta(storage_a, storage_b, fmt="{:+.1f}")),
    ]


def _reports_for(project: ClusterProject, thresholds: Thresholds):
    """build_reports() returns one SiteReport per site.site_names entry
    (dict[str, SiteReport]) since N-site support replaced the old fixed
    (primary, dr, dr_report) 3-tuple return - this project's own
    Compare table still only shows a Primary/DR-shaped view (see the
    hardcoded row labels below), so this pulls exactly those two plus
    a DR-readiness FailoverReport for the DR site, by name rather than
    by tuple position. Falls back to None for either report if the
    project doesn't actually have a site by that name (e.g. a
    Primary-only project has no "DR")."""
    from src.models.cluster_project import DR, PRIMARY
    reports = build_reports(project, thresholds)
    primary = reports.get(PRIMARY)
    dr = reports.get(DR)
    dr_readiness = build_failover_report(project, DR, thresholds) if DR in project.site_names else None
    return primary, dr, dr_readiness


def build_comparison_rows(
    project_a: ClusterProject, project_b: ClusterProject | None, thresholds: Thresholds
) -> list[tuple[str, str, str]]:
    """Returns (label, value_a, value_b) rows. value_b is '-' for every
    row when project_b is None (no Scenario B loaded yet)."""

    pa, dra, dcka = _reports_for(project_a, thresholds)
    if project_b is not None:
        pb, drb, dckb = _reports_for(project_b, thresholds)
    else:
        pb, drb, dckb = None, None, None

    def ratio(v, as_percent=False):
        if v is None:
            return "-"
        return f"{v * 100:.0f}%" if as_percent else f"{v:.2f} : 1"

    def yn(v):
        if v is None:
            return "-"
        return "Yes" if v else "No"

    def b(fn):
        return fn(pb, drb, dckb) if project_b is not None else "-"

    def ht_text(report):
        if report is None:
            return "-"
        return {
            "all_on": "HT ENABLED",
            "mixed": "HT MIXED",
            "all_off": "HT off",
            "no_servers": "-",
        }.get(report.ht_state, "-")

    rows: list[tuple[str, str, str]] = []

    rows.append(("--- PRIMARY SITE ---", "", ""))
    rows.append(("Servers", str(pa.server_count), b(lambda p, d, c: str(p.server_count))))
    rows.append(("Physical cores (HT-adj.)", str(pa.physical_cores), b(lambda p, d, c: str(p.physical_cores))))
    rows.append(("Hyperthreading", ht_text(pa), b(lambda p, d, c: ht_text(p))))
    rows.append(("Physical RAM (GB)", f"{pa.physical_ram_gb:.0f}", b(lambda p, d, c: f"{p.physical_ram_gb:.0f}")))
    rows.append(("Usable storage (TB)", f"{pa.usable_storage_gb / 1024:.1f}", b(lambda p, d, c: f"{p.usable_storage_gb / 1024:.1f}")))
    rows.append(("VM count", str(pa.vm_count), b(lambda p, d, c: str(p.vm_count))))
    rows.append(("vCPU demand (powered on)", str(pa.vcpu_demand), b(lambda p, d, c: str(p.vcpu_demand))))
    rows.append(("RAM demand (powered on, GB)", f"{pa.ram_demand_gb:.0f}", b(lambda p, d, c: f"{p.ram_demand_gb:.0f}")))
    rows.append(("Disk demand (all, TB)", f"{pa.disk_demand_gb / 1024:.1f}", b(lambda p, d, c: f"{p.disk_demand_gb / 1024:.1f}")))
    rows.append(("CPU oversubscription", f"{ratio(pa.cpu_ratio)} ({pa.cpu_status.value})", b(lambda p, d, c: f"{ratio(p.cpu_ratio)} ({p.cpu_status.value})")))
    rows.append(("RAM utilization", f"{ratio(pa.ram_ratio, True)} ({pa.ram_status.value})", b(lambda p, d, c: f"{ratio(p.ram_ratio, True)} ({p.ram_status.value})")))
    rows.append(("Storage utilization", f"{ratio(pa.storage_ratio, True)} ({pa.storage_status.value})", b(lambda p, d, c: f"{ratio(p.storage_ratio, True)} ({p.storage_status.value})")))
    rows.append(("Survives N+1", yn(pa.n_plus_one_ok), b(lambda p, d, c: yn(p.n_plus_one_ok))))

    rows.append(("--- DR SITE ---", "", ""))
    if dra is not None:
        rows.append(("Servers", str(dra.server_count), b(lambda p, d, c: str(d.server_count) if d else "-")))
        rows.append(("Physical cores (HT-adj.)", str(dra.physical_cores), b(lambda p, d, c: str(d.physical_cores) if d else "-")))
        rows.append(("Hyperthreading", ht_text(dra), b(lambda p, d, c: ht_text(d))))
        rows.append(("Physical RAM (GB)", f"{dra.physical_ram_gb:.0f}", b(lambda p, d, c: f"{d.physical_ram_gb:.0f}" if d else "-")))
        rows.append(("Usable storage (TB)", f"{dra.usable_storage_gb / 1024:.1f}", b(lambda p, d, c: f"{d.usable_storage_gb / 1024:.1f}" if d else "-")))
    else:
        rows.append(("(no DR site on Scenario A)", "-", b(lambda p, d, c: f"{d.server_count} server(s)" if d else "(no DR site)")))

    rows.append(("--- DR READINESS ---", "", ""))
    if dcka is not None:
        rows.append(("DR-protected VMs", str(dcka.assigned_vm_count), b(lambda p, d, c: str(c.assigned_vm_count) if c else "-")))
        rows.append(("Failover vCPU demand", str(dcka.failover_vcpu_demand), b(lambda p, d, c: str(c.failover_vcpu_demand) if c else "-")))
        rows.append(("Failover RAM demand (GB)", f"{dcka.failover_ram_demand_gb:.0f}", b(lambda p, d, c: f"{c.failover_ram_demand_gb:.0f}" if c else "-")))
        rows.append(("Failover disk demand (TB)", f"{dcka.failover_disk_demand_gb / 1024:.1f}", b(lambda p, d, c: f"{c.failover_disk_demand_gb / 1024:.1f}" if c else "-")))
        rows.append(("DR Ready", yn(dcka.ready), b(lambda p, d, c: yn(c.ready) if c else "-")))
    else:
        rows.append(("(no DR site on Scenario A)", "-", b(lambda p, d, c: "has DR readiness data" if c else "(no DR site)")))

    return rows
