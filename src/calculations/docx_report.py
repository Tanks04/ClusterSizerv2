"""Builds a structured Word (.docx) report from a ClusterProject - no Qt
dependency, so it's testable on its own (inspect the returned Document's
paragraphs/tables directly). Replaces the earlier PDF export: a Word
document is something the recipient can actually edit further (add a
letterhead, trim sections, rebrand for a client) rather than a
print-oriented dead end nobody was going to print anyway.

Section order: Servers -> Storage -> Network -> Cluster (config/
thresholds/DR readiness) -> Virtual Machines. Each inventory section
(Servers/Storage/Network) leads with a small aggregate table, then the
full per-device listing below it - the aggregate answers "how much do I
have", the listing answers "what exactly is it".
"""

import sys
from datetime import datetime

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor
    _docx_import_error = None
except Exception as _exc:  # noqa: BLE001 - deliberately broad, see message below
    Document = None
    WD_ALIGN_PARAGRAPH = None
    Pt = None
    RGBColor = None
    _docx_import_error = _exc

from src.calculations.sizing import build_reports
from src.calculations.thresholds import Status, Thresholds
from src.models.cluster_project import ClusterProject, PRIMARY, DR


def _docx_missing_message() -> str:
    detail = f" (underlying error: {_docx_import_error})" if _docx_import_error else ""
    return (
        "Generating a Word report requires python-docx, and it could not be imported"
        f"{detail}.\n\n"
        f"This app is running from:\n{sys.executable}\n\n"
        "If you already ran 'pip install python-docx', make sure you installed "
        "it into THIS interpreter specifically - e.g. run:\n"
        f'"{sys.executable}" -m pip install python-docx\n'
        "A different install elsewhere (system Python, another venv, VS Code's "
        "default interpreter, etc.) won't be seen by this app if it's not the "
        "same environment.\n\n"
        "Also double-check you installed 'python-docx', not the unrelated, "
        "abandoned PyPI package literally named 'docx' - both import as 'docx' "
        "at runtime, but only python-docx provides Document."
    )

# Mirrors src/gui/widgets/status_badge.py's palette - kept as its own
# copy so this module stays Qt-free (same approach html_report.py used).
# Guarded like the imports above - RGBColor(...) would itself raise at
# module-import time if docx failed to import, defeating the point of a
# soft-fail guard.
if RGBColor is not None:
    _STATUS_COLORS = {
        Status.OK: RGBColor(0x2E, 0x7D, 0x32),
        Status.WARNING: RGBColor(0xED, 0x6C, 0x02),
        Status.CRITICAL: RGBColor(0xC6, 0x28, 0x28),
        Status.UNKNOWN: RGBColor(0x75, 0x75, 0x75),
    }
    _GRAY = RGBColor(0x75, 0x75, 0x75)
    _ORANGE = RGBColor(0xED, 0x6C, 0x02)
    _RED = RGBColor(0xC6, 0x28, 0x28)
    _GREEN = RGBColor(0x2E, 0x7D, 0x32)
else:
    _STATUS_COLORS = {}
    _GRAY = _ORANGE = _RED = _GREEN = None


def _add_table(document: Document, headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        p = document.add_paragraph("None configured.")
        p.runs[0].italic = True
        p.runs[0].font.color.rgb = _GRAY
        return

    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"

    header_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        header_cells[i].text = header
        header_cells[i].paragraphs[0].runs[0].bold = True

    for row_data in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row_data):
            cells[i].text = str(value)


def _status_text(status: Status) -> tuple[str, RGBColor]:
    return status.value, _STATUS_COLORS.get(status, _GRAY)


def _add_colored_run(paragraph, text: str, color: RGBColor, bold: bool = False) -> None:
    run = paragraph.add_run(text)
    run.font.color.rgb = color
    run.bold = bold


def _yn(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "Yes" if value else "No"


def _servers_section(document: Document, project: ClusterProject) -> None:
    document.add_heading("Servers", level=1)

    document.add_heading("Summary", level=2)
    agg_rows = []
    for site in (PRIMARY, DR):
        site_servers = [s for s in project.servers if s.site == site]
        enabled_servers = [s for s in site_servers if s.enabled]
        agg_rows.append([
            site,
            str(len(enabled_servers)),
            str(project.physical_cores(site)),
            str(sum(s.total_cores for s in enabled_servers)),
            f"{project.physical_ram_gb(site):.0f} GB",
        ])
    _add_table(document, ["Site", "Servers (enabled)", "Effective Cores (HT-adj.)", "Physical Cores", "RAM"], agg_rows)

    document.add_heading("All Servers", level=2)
    rows = []
    for s in project.servers:
        rows.append([
            s.name, s.site, s.vendor or "-", s.model or "-",
            f"{s.sockets}x{s.cores_per_socket}", "Yes" if s.hyperthreading_enabled else "No",
            str(s.effective_cores), f"{s.ram_gb} GB",
            "Enabled" if s.enabled else "Disabled",
        ])
    _add_table(document, ["Name", "Site", "Vendor", "Model", "Sockets x Cores", "HT", "Effective Cores", "RAM", "Status"], rows)


def _storage_section(document: Document, project: ClusterProject) -> None:
    document.add_heading("Storage", level=1)

    document.add_heading("Summary", level=2)
    agg_rows = []
    for site in (PRIMARY, DR):
        site_storages = [s for s in project.storages if s.site == site]
        agg_rows.append([
            site,
            str(len(site_storages)),
            f"{sum(s.raw_capacity_tb for s in site_storages):.1f} TB",
            f"{sum(s.usable_capacity_tb for s in site_storages):.1f} TB",
        ])
    _add_table(document, ["Site", "Storage Systems", "Raw", "Usable"], agg_rows)

    document.add_heading("All Storage Systems", level=2)
    rows = []
    for s in project.storages:
        rows.append([
            s.name, s.site, s.vendor or "-", s.model or "-",
            f"{s.raw_capacity_tb:.1f} TB", f"{s.usable_capacity_tb:.1f} TB",
            f"{s.raid_overhead_percent:.0f}%",
        ])
    _add_table(document, ["Name", "Site", "Vendor", "Model", "Raw", "Usable", "Overhead"], rows)


def _network_section(document: Document, project: ClusterProject) -> None:
    document.add_heading("Network", level=1)

    document.add_heading("Summary", level=2)
    agg_rows = []
    for site in (PRIMARY, DR):
        site_switches = [s for s in project.switches if s.site == site]
        site_connections = [
            c for c in project.connections
            if any(sw.uid == c.switch_uid for sw in site_switches)
        ]
        agg_rows.append([site, str(len(site_switches)), str(len(site_connections))])
    _add_table(document, ["Site", "Switches", "Connections (via site switches)"], agg_rows)

    document.add_heading("Switches", level=2)
    switch_rows = [
        [sw.name, sw.site, sw.vendor or "-", sw.model or "-", sw.switch_type, str(sw.total_ports)]
        for sw in project.switches
    ]
    _add_table(document, ["Name", "Site", "Vendor", "Model", "Type", "Total Ports"], switch_rows)

    document.add_heading("Connections", level=2)
    server_names = {s.uid: s.name for s in project.servers}
    switch_names = {s.uid: s.name for s in project.switches}
    storage_names = {s.uid: s.name for s in project.storages}
    conn_rows = []
    for c in project.connections:
        endpoint_a = server_names.get(c.server_uid) or storage_names.get(c.storage_uid) or "-"
        endpoint_b = switch_names.get(c.switch_uid) or storage_names.get(c.storage_uid) or "-"
        conn_rows.append([c.connection_kind, endpoint_a, endpoint_b, c.speed, c.media, c.purpose])
    _add_table(document, ["Type", "Endpoint A", "Endpoint B", "Speed", "Media", "Purpose"], conn_rows)


def _cluster_section(document: Document, project: ClusterProject, thresholds: Thresholds) -> None:
    document.add_heading("Cluster", level=1)

    primary, dr, dr_check = build_reports(project, thresholds)

    for label, report in (("Primary Site", primary), ("DR Site", dr)):
        document.add_heading(label, level=2)

        rows = [
            ("Servers", str(report.server_count)),
            ("Physical cores (HT-adj.)", str(report.physical_cores)),
            ("Physical RAM", f"{report.physical_ram_gb:.0f} GB"),
            ("Usable storage", f"{report.usable_storage_gb / 1024:.1f} TB"),
            ("VM count", str(report.vm_count)),
            ("vCPU demand (powered on)", str(report.vcpu_demand)),
            ("RAM demand (powered on)", f"{report.ram_demand_gb:.0f} GB"),
            ("Disk demand (all)", f"{report.disk_demand_gb / 1024:.1f} TB"),
        ]
        for name, value in rows:
            p = document.add_paragraph()
            p.add_run(f"{name}: ").bold = True
            p.add_run(value)

        for metric_name, ratio, status, as_percent in (
            ("CPU oversubscription", report.cpu_ratio, report.cpu_status, False),
            ("RAM utilization", report.ram_ratio, report.ram_status, True),
            ("Storage utilization", report.storage_ratio, report.storage_status, True),
        ):
            p = document.add_paragraph()
            p.add_run(f"{metric_name}: ").bold = True
            if ratio is None:
                p.add_run("n/a")
            else:
                value_text = f"{ratio * 100:.0f}%" if as_percent else f"{ratio:.2f} : 1"
                p.add_run(f"{value_text} ")
                text, color = _status_text(status)
                _add_colored_run(p, f"({text})", color, bold=True)

        p = document.add_paragraph()
        p.add_run("Survives 1 host failure (N+1): ").bold = True
        p.add_run(_yn(report.n_plus_one_ok))
        if report.n_plus_one_ok is False and report.n_plus_one_check is not None:
            check = report.n_plus_one_check
            shortfalls = []
            if not check.ram_ok:
                shortfalls.append(f"+{check.ram_shortfall_gb:.0f} GB RAM")
            if not check.cpu_ok:
                shortfalls.append(f"+{check.cpu_shortfall_effective_cores:.0f} effective CPU cores")
            if shortfalls:
                detail = document.add_paragraph()
                _add_colored_run(detail, f"Would need {' and '.join(shortfalls)} to survive losing a host.", _ORANGE)

    document.add_heading("DR Readiness (failover Primary \u2192 DR)", level=2)
    dr_rows = [
        ("DR-protected VMs", str(dr_check.protected_vm_count)),
        ("Failover vCPU demand", str(dr_check.failover_vcpu_demand)),
        ("Failover RAM demand", f"{dr_check.failover_ram_demand_gb:.0f} GB"),
        ("Failover disk demand", f"{dr_check.failover_disk_demand_gb / 1024:.1f} TB"),
    ]
    for name, value in dr_rows:
        p = document.add_paragraph()
        p.add_run(f"{name}: ").bold = True
        p.add_run(value)
    p = document.add_paragraph()
    p.add_run("DR Ready: ").bold = True
    ready_text = _yn(dr_check.ready)
    ready_color = _GREEN if dr_check.ready else (_RED if dr_check.ready is False else _GRAY)
    _add_colored_run(p, ready_text, ready_color, bold=True)

    document.add_heading("Assumptions", level=2)
    assumptions = document.add_paragraph()
    assumptions.add_run(
        f"CPU warning/critical: {thresholds.cpu_warning_ratio:.1f}:1 / {thresholds.cpu_critical_ratio:.1f}:1  \u00b7  "
        f"RAM warning/critical: {thresholds.ram_warning_ratio * 100:.0f}% / {thresholds.ram_critical_ratio * 100:.0f}%  \u00b7  "
        f"Storage warning/critical: {thresholds.storage_warning_ratio * 100:.0f}% / {thresholds.storage_critical_ratio * 100:.0f}%"
    ).italic = True


def _vms_section(document: Document, project: ClusterProject) -> None:
    document.add_heading("Virtual Machines", level=1)

    rows = []
    for vm in project.vms:
        rows.append([
            vm.name, vm.site, str(vm.vcpu), f"{vm.ram_gb:.0f} GB", f"{vm.disk_gb:.0f} GB",
            vm.workload_tier, "Yes" if vm.dr_protected else "No",
            "On" if vm.powered_on else "Off",
        ])
    _add_table(document, ["Name", "Site", "vCPU", "RAM", "Disk", "Workload Tier", "DR Protected", "Power"], rows)


def build_docx_report(project: ClusterProject, thresholds: Thresholds, app_version: str = "") -> "Document":
    if Document is None:
        raise ImportError(_docx_missing_message())

    document = Document()

    title = document.add_heading(project.name or "Untitled Project", level=0)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    version_line = f"ClusterSizer {app_version}" if app_version else "ClusterSizer"
    subtitle = document.add_paragraph(f"Generated {generated}  \u00b7  {version_line}")
    subtitle.runs[0].italic = True
    subtitle.runs[0].font.color.rgb = _GRAY

    _servers_section(document, project)
    document.add_page_break()
    _storage_section(document, project)
    document.add_page_break()
    _network_section(document, project)
    document.add_page_break()
    _cluster_section(document, project, thresholds)
    document.add_page_break()
    _vms_section(document, project)

    return document
