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
from src.calculations.sizing import build_reports
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

    primary_report, dr_report, dr_check = build_reports(project, thresholds)

    for report in (primary_report, dr_report):
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

    if dr_check.ready is False:
        items.append(AttentionItem(
            Status.CRITICAL,
            "DR Readiness: DR site does not have enough capacity for full failover",
        ))

    # Skip nagging about backup compliance for a project with no VMs yet
    # (nothing to back up) - avoids noise on a brand new, still-empty project.
    if project.vms:
        backup_check = compute_compliance(project.backup_destinations)
        if not backup_check.meets_3_2_1_1:
            for gap in backup_check.missing:
                items.append(AttentionItem(Status.WARNING, f"Backup: {gap}"))

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
