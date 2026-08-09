from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.calculations.sizing import build_reports
from src.services.project_service import ProjectService

from ..widgets.site_capacity_widget import SiteCapacityWidget
from ..widgets.status_badge import StatusBadge
from ..widgets.summary_widget import SummaryWidget


class SummaryPage(QWidget):
    """Combined overview: a compact top-line card row (formerly its own
    Dashboard tab - merged in here since it's the same "quick glance at
    the whole project" purpose as the detailed view below it, just one
    tab instead of two) followed by the deep-dive Primary vs DR breakdown,
    oversubscription, and DR readiness. This is the page that answers
    "do I have enough resources?"."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()

        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        #
        # Compact top-line cards (formerly the Dashboard tab)
        #

        self.title_label = QLabel("ClusterSizer")
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(16)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Capacity planning for virtualized infrastructure")
        self.subtitle_label.setStyleSheet("color: #757575;")
        layout.addWidget(self.subtitle_label)

        top_grid = QGridLayout()
        layout.addLayout(top_grid)

        self.card_servers = SummaryWidget("Servers (Total)", "0", compact=True)
        self.card_cores = SummaryWidget("Cores (Total)", "0", compact=True)
        self.card_ram = SummaryWidget("RAM (Total)", "0 GB", compact=True)
        self.card_storage = SummaryWidget("Usable Storage (Total)", "0 TB", compact=True)
        self.card_vms = SummaryWidget("VMs (Total)", "0", compact=True)
        self.card_primary_servers = SummaryWidget("Primary Servers", "0", compact=True)
        self.card_dr_servers = SummaryWidget("DR Servers", "0", compact=True)
        self.card_dr_ready = SummaryWidget("DR Ready", "-", compact=True)

        top_cards = [
            self.card_servers, self.card_cores, self.card_ram, self.card_storage,
            self.card_vms, self.card_primary_servers, self.card_dr_servers, self.card_dr_ready,
        ]
        for i, card in enumerate(top_cards):
            top_grid.addWidget(card, i // 4, i % 4)

        #
        # Deep-dive: Primary vs DR
        #

        summary_title = QLabel("Cluster Summary")
        summary_title_font = summary_title.font()
        summary_title_font.setBold(True)
        summary_title_font.setPointSize(16)
        summary_title.setFont(summary_title_font)
        layout.addWidget(summary_title)

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

        #
        # Top-line cards
        #

        self.title_label.setText(project.name or "ClusterSizer")

        self.card_servers.set_value(project.server_count)
        self.card_cores.set_value(project.total_cores)
        self.card_ram.set_value(f"{project.total_ram} GB")

        total_storage_tb = (
            project.usable_storage_gb(PRIMARY) + project.usable_storage_gb(DR)
        ) / 1024
        self.card_storage.set_value(f"{total_storage_tb:.1f} TB")

        self.card_vms.set_value(len(project.vms))
        self.card_primary_servers.set_value(len(project.servers_at(PRIMARY)))
        self.card_dr_servers.set_value(len(project.servers_at(DR)))

        ready = project.dr_ready()
        if ready is None:
            self.card_dr_ready.set_value("n/a")
        else:
            self.card_dr_ready.set_value("Yes" if ready else "No")

        #
        # Deep-dive
        #

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
