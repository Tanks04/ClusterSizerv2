from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.calculations.sizing import build_reports
from src.calculations.docx_report import build_docx_report
from src.services.project_service import ProjectService
from src.version import VERSION
from src.gui.error_handling import report_error


def _fmt_ratio(ratio: float | None, as_percent: bool = False) -> str:
    if ratio is None:
        return "n/a"
    return f"{ratio * 100:.0f}%" if as_percent else f"{ratio:.2f} : 1"


def _fmt_bool(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "YES" if value else "NO"


class ReportsPage(QWidget):
    """Generates a readable text report of the whole project, ready for
    export or copy-paste into a ticket/email."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()

        self.service.changed.connect(self._generate)
        self._generate()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        buttons = QHBoxLayout()

        generate_button = QPushButton("🔄 Refresh Report")
        generate_button.clicked.connect(self._generate)
        buttons.addWidget(generate_button)

        export_txt_button = QPushButton("📤 Export Report (.txt)")
        export_txt_button.clicked.connect(self._export_txt)
        buttons.addWidget(export_txt_button)

        export_docx_button = QPushButton("📄 Export Word Report")
        export_docx_button.setToolTip(
            "A structured, editable Word document - Servers, Storage, Network, "
            "Cluster config, and VMs, each with a summary plus the full "
            "per-device listing. Add a letterhead, trim sections, or rebrand "
            "for a client afterward."
        )
        export_docx_button.clicked.connect(self._export_docx)
        buttons.addWidget(export_docx_button)

        export_all_button = QPushButton("📤 Export All Data (CSV bundle)")
        export_all_button.clicked.connect(self._export_all_csv)
        buttons.addWidget(export_all_button)

        buttons.addStretch()

        layout.addLayout(buttons)

        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Courier New"))
        layout.addWidget(self.text_area)

    def _build_report_text(self) -> str:
        from src.models.cluster_project import PRIMARY, DR

        project = self.service.project
        thresholds = self.service.thresholds

        primary, dr, dr_check = build_reports(project, thresholds)

        lines = []
        lines.append(f"ClusterSizer {VERSION} Report - {project.name}")
        lines.append("=" * 60)
        lines.append("")

        for label, report in (("PRIMARY", primary), ("DR", dr)):
            lines.append(f"[{label}]")
            lines.append(f"  Servers            : {report.server_count}")
            ht_tag = {"all_on": " [HT ENABLED]", "mixed": " [HT MIXED]"}.get(report.ht_state, "")
            lines.append(f"  Physical cores (HT-adj.): {report.physical_cores}{ht_tag}")
            lines.append(f"  Physical threads    : {report.physical_threads}")
            lines.append(f"  Physical RAM        : {report.physical_ram_gb:.0f} GB")
            lines.append(f"  Usable storage      : {report.usable_storage_gb / 1024:.2f} TB")
            lines.append(f"  VM count            : {report.vm_count}")
            lines.append(f"  vCPU demand (on)    : {report.vcpu_demand}")
            lines.append(f"  RAM demand (on)     : {report.ram_demand_gb:.0f} GB")
            lines.append(f"  Disk demand (all)   : {report.disk_demand_gb / 1024:.2f} TB")
            lines.append(f"  CPU oversubscription: {_fmt_ratio(report.cpu_ratio)} ({report.cpu_status.value})")
            lines.append(f"  RAM utilization     : {_fmt_ratio(report.ram_ratio, True)} ({report.ram_status.value})")
            lines.append(f"  Storage utilization : {_fmt_ratio(report.storage_ratio, True)} ({report.storage_status.value})")
            lines.append(f"  Survives N+1        : {_fmt_bool(report.n_plus_one_ok)}")
            if report.n_plus_one_ok is False and report.n_plus_one_check is not None:
                check = report.n_plus_one_check
                shortfalls = []
                if not check.ram_ok:
                    shortfalls.append(f"+{check.ram_shortfall_gb:.0f} GB RAM")
                if not check.cpu_ok:
                    shortfalls.append(f"+{check.cpu_shortfall_effective_cores:.0f} effective CPU cores")
                if shortfalls:
                    lines.append(f"    (would need {' and '.join(shortfalls)} to survive losing a host)")
            lines.append("")

        lines.append("[DR READINESS] (failover Primary -> DR)")
        lines.append(f"  DR-protected VMs    : {dr_check.protected_vm_count}")
        lines.append(f"  Failover vCPU (on)  : {dr_check.failover_vcpu_demand}")
        lines.append(f"  Failover RAM (on)   : {dr_check.failover_ram_demand_gb:.0f} GB")
        lines.append(f"  Failover disk demand: {dr_check.failover_disk_demand_gb / 1024:.2f} TB")
        lines.append(f"  CPU OK      : {_fmt_bool(dr_check.cpu_ok)}")
        lines.append(f"  RAM OK      : {_fmt_bool(dr_check.ram_ok)}")
        lines.append(f"  Storage OK  : {_fmt_bool(dr_check.storage_ok)}")
        lines.append(f"  DR READY    : {_fmt_bool(dr_check.ready)}")

        return "\n".join(lines)

    def _generate(self):
        self.text_area.setPlainText(self._build_report_text())

    def _export_txt(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Report", "report.txt", "Text (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(self._build_report_text(), encoding="utf-8")
            QMessageBox.information(self, "Export", "Report exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _export_docx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Word Report", "report.docx", "Word Document (*.docx)")
        if not path:
            return
        if not path.lower().endswith(".docx"):
            path += ".docx"

        try:
            document = build_docx_report(
                self.service.project, self.service.thresholds, app_version=VERSION,
            )
            document.save(path)
            QMessageBox.information(self, "Export", "Word report exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _export_all_csv(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not folder:
            return
        try:
            self.service.export_servers_csv(Path(folder) / "servers.csv")
            self.service.export_storages_csv(Path(folder) / "storage.csv")
            self.service.export_vms_csv(Path(folder) / "vms.csv")
            self.service.export_switches_csv(Path(folder) / "switches.csv")
            self.service.export_connections_csv(Path(folder) / "connections.csv")
            QMessageBox.information(
                self, "Export",
                "servers.csv, storage.csv, vms.csv, switches.csv, and "
                "connections.csv have been saved.",
            )
        except Exception as exc:
            report_error(self, "Export Error", exc)
