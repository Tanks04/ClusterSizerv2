from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.calculations.sizing import build_reports
from src.services.project_service import ProjectService

from ..widgets.site_capacity_widget import SiteCapacityWidget
from ..widgets.status_badge import StatusBadge


class SummaryPage(QWidget):
    """Deep-dive view: Primary vs DR, oversubscription, DR readiness.
    This is the page that answers "do I have enough resources?"."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()

        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Cluster Summary")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title.setFont(title_font)
        layout.addWidget(title)

        sites_layout = QHBoxLayout()

        self.primary_card = SiteCapacityWidget("Primary")
        self.dr_card = SiteCapacityWidget("DR")

        sites_layout.addWidget(self.primary_card)
        sites_layout.addWidget(self.dr_card)

        layout.addLayout(sites_layout)

        #
        # DR readiness
        #

        dr_layout = QHBoxLayout()

        dr_title = QLabel("DR Readiness (full failover Primary \u2192 DR):")
        dr_title_font = dr_title.font()
        dr_title_font.setBold(True)
        dr_title.setFont(dr_title_font)
        dr_layout.addWidget(dr_title)

        self.dr_badge = StatusBadge()
        dr_layout.addWidget(self.dr_badge)

        dr_layout.addStretch()

        layout.addLayout(dr_layout)

        self.dr_detail_label = QLabel("-")
        self.dr_detail_label.setWordWrap(True)
        layout.addWidget(self.dr_detail_label)

        layout.addStretch()

    def refresh(self):
        from src.calculations.thresholds import Status
        from src.models.cluster_project import PRIMARY, DR

        project = self.service.project
        thresholds = self.service.thresholds

        primary_report, dr_report, dr_check = build_reports(project, thresholds)

        self.primary_card.set_report(primary_report)
        self.dr_card.set_report(dr_report)

        if dr_check.ready is None:
            self.dr_badge.set_status(Status.UNKNOWN)
            self.dr_detail_label.setText(
                "No servers/storage defined at the DR site - add them on the "
                "Servers/Storage pages to calculate DR readiness."
            )
        elif dr_check.ready:
            self.dr_badge.set_status(Status.OK)
            self.dr_detail_label.setText(
                f"The DR site has enough capacity for failover: "
                f"{dr_check.protected_vm_count} DR-protected VM(s) (+ what's already "
                f"running on DR) need {dr_check.failover_vcpu_demand} vCPU / "
                f"{dr_check.failover_ram_demand_gb:.0f} GB / "
                f"{dr_check.failover_disk_demand_gb / 1024:.1f} TB."
            )
        else:
            self.dr_badge.set_status(Status.CRITICAL)
            problems = []
            if dr_check.cpu_ok is False:
                problems.append("CPU")
            if dr_check.ram_ok is False:
                problems.append("RAM")
            if dr_check.storage_ok is False:
                problems.append("Storage")
            self.dr_detail_label.setText(
                f"The DR site does NOT have enough capacity for failover. Missing: "
                f"{', '.join(problems)}. Demand: {dr_check.protected_vm_count} "
                f"DR-protected VM(s) ({dr_check.failover_vcpu_demand} vCPU / "
                f"{dr_check.failover_ram_demand_gb:.0f} GB / "
                f"{dr_check.failover_disk_demand_gb / 1024:.1f} TB)."
            )
