"""Builds a styled HTML report from a ClusterProject - no Qt dependency,
so it's testable on its own. The GUI layer (reports_page.py) feeds this
HTML into a QTextDocument and prints that to PDF via QPrinter, using Qt's
own built-in printing support instead of pulling in a PDF library as a
new dependency.

The HTML is deliberately old-school (nested <table>s, inline styles, no
flexbox/grid) because QTextDocument's HTML renderer only supports a
fairly basic CSS subset - anything relying on modern layout wouldn't
render right in the exported PDF.
"""

from datetime import datetime

from src.calculations.sizing import build_reports, SiteReport, DRReport
from src.calculations.thresholds import Status, Thresholds
from src.models.cluster_project import ClusterProject

# Mirrors src/gui/widgets/status_badge.py's palette - kept as its own
# copy here rather than importing that (Qt) widget module, so this stays
# Qt-free and testable without PySide6 installed.
_STATUS_COLORS = {
    Status.OK: "#2e7d32",
    Status.WARNING: "#ed6c02",
    Status.CRITICAL: "#c62828",
    Status.UNKNOWN: "#757575",
}

_HT_COLORS = {
    "all_on": "#c62828",   # red, bold - see site_capacity_widget.py for the reasoning
    "mixed": "#ed6c02",    # orange, bold
}
_HT_LABELS = {
    "all_on": "HT ENABLED",
    "mixed": "HT MIXED",
}


def _status_badge(status: Status) -> str:
    color = _STATUS_COLORS.get(status, _STATUS_COLORS[Status.UNKNOWN])
    return (
        f'<span style="background-color:{color}; color:white; '
        f'padding:2px 8px; border-radius:4px; font-weight:bold; '
        f'font-size:11px;">{status.value}</span>'
    )


def _ht_tag(ht_state: str) -> str:
    if ht_state not in _HT_LABELS:
        return ""
    color = _HT_COLORS[ht_state]
    return f' <span style="color:{color}; font-weight:bold;">[{_HT_LABELS[ht_state]}]</span>'


def _yn_badge(value: bool | None) -> str:
    if value is None:
        return '<span style="color:#757575;">n/a</span>'
    if value:
        return '<span style="color:#2e7d32; font-weight:bold;">Yes</span>'
    return '<span style="color:#c62828; font-weight:bold;">No</span>'


def _site_table(title: str, report: SiteReport) -> str:
    rows = [
        ("Servers", str(report.server_count)),
        ("Physical cores (HT-adj.)", f"{report.physical_cores}{_ht_tag(report.ht_state)}"),
        ("Physical RAM", f"{report.physical_ram_gb:.0f} GB"),
        ("Usable storage", f"{report.usable_storage_gb / 1024:.1f} TB"),
        ("VM count", str(report.vm_count)),
        ("vCPU demand (powered on)", str(report.vcpu_demand)),
        ("RAM demand (powered on)", f"{report.ram_demand_gb:.0f} GB"),
        ("Disk demand (all)", f"{report.disk_demand_gb / 1024:.1f} TB"),
        ("CPU oversubscription", f"{report.cpu_ratio:.2f} : 1 {_status_badge(report.cpu_status)}" if report.cpu_ratio is not None else "n/a"),
        ("RAM utilization", f"{report.ram_ratio * 100:.0f}% {_status_badge(report.ram_status)}" if report.ram_ratio is not None else "n/a"),
        ("Storage utilization", f"{report.storage_ratio * 100:.0f}% {_status_badge(report.storage_status)}" if report.storage_ratio is not None else "n/a"),
        ("Survives N+1", _yn_badge(report.n_plus_one_ok)),
    ]

    row_html = "".join(
        f'<tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">{label}</td>'
        f'<td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; font-weight:bold;">{value}</td></tr>'
        for label, value in rows
    )

    return f'''
    <h2 style="color:#1976d2; margin-top:24px;">{title}</h2>
    <table style="border-collapse:collapse; width:100%;">
      {row_html}
    </table>
    '''


def _dr_readiness_table(dr_check: DRReport) -> str:
    checks = [
        ("CPU", dr_check.cpu_ok),
        ("RAM", dr_check.ram_ok),
        ("Storage", dr_check.storage_ok),
    ]
    row_html = "".join(
        f'<tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">{label} OK</td>'
        f'<td style="padding:6px 12px; border-bottom:1px solid #e0e0e0;">{_yn_badge(ok)}</td></tr>'
        for label, ok in checks
    )

    return f'''
    <h2 style="color:#1976d2; margin-top:24px;">DR Readiness (failover Primary \u2192 DR)</h2>
    <table style="border-collapse:collapse; width:100%; margin-bottom:12px;">
      <tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">DR-protected VMs</td>
          <td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; font-weight:bold;">{dr_check.protected_vm_count}</td></tr>
      <tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">Failover vCPU demand</td>
          <td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; font-weight:bold;">{dr_check.failover_vcpu_demand}</td></tr>
      <tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">Failover RAM demand</td>
          <td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; font-weight:bold;">{dr_check.failover_ram_demand_gb:.0f} GB</td></tr>
      <tr><td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; color:#555;">Failover disk demand</td>
          <td style="padding:6px 12px; border-bottom:1px solid #e0e0e0; font-weight:bold;">{dr_check.failover_disk_demand_gb / 1024:.1f} TB</td></tr>
      {row_html}
      <tr><td style="padding:8px 12px; font-weight:bold; font-size:14px;">DR READY</td>
          <td style="padding:8px 12px;">{_yn_badge(dr_check.ready)}</td></tr>
    </table>
    '''


def build_html_report(project: ClusterProject, thresholds: Thresholds, app_version: str = "") -> str:
    primary, dr, dr_check = build_reports(project, thresholds)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    version_line = f"ClusterSizer {app_version}" if app_version else "ClusterSizer"

    return f'''
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; color:#212121;">
      <h1 style="color:#1976d2; margin-bottom:0;">{project.name or "Untitled Project"}</h1>
      <p style="color:#757575; margin-top:4px;">Generated {generated} &middot; {version_line}</p>
      {_site_table("Primary Site", primary)}
      {_site_table("DR Site", dr)}
      {_dr_readiness_table(dr_check)}
      <p style="color:#9e9e9e; font-size:11px; margin-top:32px;">
        Capacity planning report generated by ClusterSizer.
      </p>
    </body>
    </html>
    '''
