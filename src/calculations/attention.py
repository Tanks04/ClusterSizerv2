"""Aggregates every existing "is something wrong" status already
computed elsewhere in the app into one list - CPU/RAM/Storage
oversubscription, N+1, DR Readiness, backup 3-2-1-1 compliance, and
Maintenance Item expiry - so a periodic project review doesn't require
clicking through 4-5 different tabs to see if anything needs attention.

Deliberately adds no new calculations of its own - every item here is
sourced from a function that already exists and is already tested
elsewhere (sizing.py, backup.py, pricing.py). This module only decides
which of those statuses are "actionable" (Warning/Critical) versus
fine (OK) or not yet meaningful (Unknown - no data entered yet), and
turns them into one flat, severity-sorted list of short messages.
"""

from dataclasses import dataclass

from src.calculations.thresholds import Status, Thresholds
from src.calculations.sizing import build_reports, build_failover_report
from src.calculations.backup import compute_compliance
from src.calculations.pricing import compute_maintenance_status
from src.models.cluster_project import ClusterProject

_SEVERITY_ORDER = {Status.CRITICAL: 0, Status.WARNING: 1}


@dataclass
class AttentionItem:
    severity: Status  # only ever WARNING or CRITICAL - OK/Unknown are never "attention needed"
    message: str


def compute_attention_items(project: ClusterProject, thresholds: Thresholds) -> list[AttentionItem]:
    items: list[AttentionItem] = []

    reports = build_reports(project, thresholds)

    for site in project.site_names:
        report = reports[site]
        if report.cpu_status in (Status.WARNING, Status.CRITICAL):
            ratio_text = f"{report.cpu_ratio:.1f}:1" if report.cpu_ratio is not None else "n/a"
            items.append(AttentionItem(
                report.cpu_status,
                f"{report.site}: CPU oversubscription is {ratio_text} ({report.cpu_status.value})",
            ))
        if report.ram_status in (Status.WARNING, Status.CRITICAL):
            pct_text = f"{report.ram_ratio * 100:.0f}%" if report.ram_ratio is not None else "n/a"
            items.append(AttentionItem(
                report.ram_status,
                f"{report.site}: RAM utilization is {pct_text} ({report.ram_status.value})",
            ))
        if report.storage_status in (Status.WARNING, Status.CRITICAL):
            pct_text = f"{report.storage_ratio * 100:.0f}%" if report.storage_ratio is not None else "n/a"
            items.append(AttentionItem(
                report.storage_status,
                f"{report.site}: Storage utilization is {pct_text} ({report.storage_status.value})",
            ))
        if report.disk_demand_gb > 0 and report.usable_storage_gb == 0:
            # Distinct from the ordinary storage_status Unknown case (which
            # covers a genuinely empty site with nothing entered at all,
            # and is deliberately never flagged) - this is real VM disk
            # demand with NOWHERE for it to actually live: no Storage
            # entity, and no server-local disk (HCI) either. A blind spot
            # in the sizing, not just "tight but assessable."
            items.append(AttentionItem(
                Status.CRITICAL,
                f"{report.site}: {report.disk_demand_gb / 1024:.1f} TB of VM disk demand, but no "
                "storage capacity entered anywhere (Storage tab or server local disk)",
            ))
        if report.n_plus_one_ok is False:
            check = report.n_plus_one_check
            shortfalls = []
            if check is not None and not check.cpu_ok:
                shortfalls.append(f"{check.cpu_shortfall_effective_cores:.0f} effective cores")
            if check is not None and not check.ram_ok:
                shortfalls.append(f"{check.ram_shortfall_gb:.0f} GB RAM")
            detail = " and ".join(shortfalls) if shortfalls else "capacity"
            items.append(AttentionItem(
                Status.WARNING,
                f"{report.site}: would NOT survive losing 1 host (short {detail})",
            ))

        failover = build_failover_report(project, site, thresholds)
        if failover.ready is False:
            items.append(AttentionItem(
                Status.CRITICAL,
                f"{site}: does not have enough capacity for its assigned failover VMs",
            ))

    for storage in project.storages:
        if storage.raw_capacity_tb > 0 and storage.usable_capacity_tb == 0:
            # Found directly from a real project: an HCI storage entry
            # with Raw auto-summed to 48TB from its linked servers, but
            # Usable left at 0 (its deliberate reset-on-HCI-checked
            # default, meant to force a real number rather than leave a
            # misleading stale one - but nothing stops saving before
            # actually filling it in). Every capacity check in the app
            # uses Usable, never Raw, so this entity silently contributes
            # NOTHING anywhere until a real usable number is entered.
            items.append(AttentionItem(
                Status.WARNING,
                f"Storage '{storage.name}' has {storage.raw_capacity_tb:.1f} TB raw capacity "
                "entered, but Usable Capacity is still 0 - it won't count toward any "
                "capacity check until a real usable number is entered.",
            ))

        pool_ratio = project.storage_pool_utilization_ratio(storage)
        if pool_ratio is not None:
            pool_status = thresholds.storage_status(pool_ratio)
            if pool_status in (Status.WARNING, Status.CRITICAL):
                # The whole reason this exists: a site's AGGREGATE storage
                # can look perfectly healthy while one SPECIFIC pool
                # (VMs assigned via VirtualMachine.storage_uid) is
                # dangerously full - the aggregate check above would
                # never catch this on its own.
                items.append(AttentionItem(
                    pool_status,
                    f"Storage '{storage.name}': assigned VMs are using "
                    f"{pool_ratio * 100:.0f}% of its usable capacity ({pool_status.value})",
                ))

    # Skip nagging about backup compliance for a project with no VMs yet
    # (nothing to back up) - avoids noise on a brand new, still-empty project.
    if project.vms:
        backup_check = compute_compliance(project.backup_destinations)
        if not backup_check.meets_3_2_1_1:
            for gap in backup_check.missing:
                items.append(AttentionItem(Status.WARNING, f"Backup: {gap}"))

    vm_by_uid = {v.uid: v for v in project.vms}
    for a in project.failover_assignments:
        if a.footprint_confirmed:
            continue
        vm = vm_by_uid.get(a.vm_uid)
        if vm is None:
            continue
        # Only flag an assignment that RESERVES MORE than the VM's current
        # size - a smaller footprint is the normal, intentional pattern
        # for a budget/constrained failover target and must never be
        # flagged. An assignment exceeding the VM's own live size has no
        # ordinary justification and most likely means the VM was resized
        # down after the assignment was created (or the assignment was
        # never updated when the VM was upsized elsewhere) - the assignment
        # just wasn't kept in sync.
        if a.vcpu > vm.vcpu or a.ram_gb > vm.ram_gb or a.disk_gb > vm.disk_gb:
            items.append(AttentionItem(
                Status.WARNING,
                f"Failover assignment for '{vm.name}' to {a.target_site} "
                f"({a.vcpu} vCPU/{a.ram_gb:.0f} GB/{a.disk_gb:.0f} GB) exceeds the "
                f"VM's current size ({vm.vcpu} vCPU/{vm.ram_gb:.0f} GB/{vm.disk_gb:.0f} GB) "
                "- may be out of date.",
            ))

    for status in compute_maintenance_status(project):
        if status.status == "expired":
            days = abs(status.days_until_expiry) if status.days_until_expiry is not None else None
            detail = f" ({days}d ago)" if days is not None else ""
            items.append(AttentionItem(
                Status.CRITICAL, f"Maintenance: '{status.item.name}' expired{detail}",
            ))
        elif status.status == "expiring_soon":
            detail = f" (in {status.days_until_expiry}d)" if status.days_until_expiry is not None else ""
            items.append(AttentionItem(
                Status.WARNING, f"Maintenance: '{status.item.name}' expiring soon{detail}",
            ))

    items.sort(key=lambda i: _SEVERITY_ORDER.get(i.severity, 2))
    return items
