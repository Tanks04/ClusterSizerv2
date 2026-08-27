from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.calculations.sizing import build_reports, build_dr_failover_report
from src.calculations.rack import compute_rack_sizing
from src.services.project_service import ProjectService

from src.gui.widgets.site_capacity_widget import SiteCapacityWidget
from src.gui.widgets.status_badge import StatusBadge
from src.gui.widgets.summary_widget import SummaryWidget


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

        summary_header = QHBoxLayout()

        summary_title = QLabel("Cluster Summary")
        summary_title_font = summary_title.font()
        summary_title_font.setBold(True)
        summary_title_font.setPointSize(16)
        summary_title.setFont(summary_title_font)
        summary_header.addWidget(summary_title)

        summary_header.addStretch()

        self.dr_failover_toggle_button = QPushButton("Preview DR Failover")
        self.dr_failover_toggle_button.setCheckable(True)
        self.dr_failover_toggle_button.setToolTip(
            "Shows what the DR card WOULD look like if every DR-protected VM "
            "were activated there right now (e.g. a Veeam/backup-driven DR "
            "plan) - same physical DR hardware, but demand includes the "
            "failover load, not just what's actually running on DR today."
        )
        self.dr_failover_toggle_button.toggled.connect(self._on_dr_failover_toggle)
        summary_header.addWidget(self.dr_failover_toggle_button)

        layout.addLayout(summary_header)

        sites_layout = QHBoxLayout()

        self.primary_card = SiteCapacityWidget("Primary")
        self.dr_card = SiteCapacityWidget("DR")

        sites_layout.addWidget(self.primary_card)
        sites_layout.addWidget(self.dr_card)

        layout.addLayout(sites_layout)

        self.dr_failover_note_label = QLabel(
            "\u26a0 Showing the DR FAILOVER scenario - live DR load + every DR-protected VM's footprint, "
            "not what's actually running on DR right now."
        )
        self.dr_failover_note_label.setStyleSheet("color: #ed6c02; font-weight: bold;")
        self.dr_failover_note_label.setWordWrap(True)
        self.dr_failover_note_label.setVisible(False)
        layout.addWidget(self.dr_failover_note_label)

        #
        # Rack sizing - optional, only meaningful once someone has
        # entered Rack Size/Power on at least some equipment. Hidden by
        # default behind a toggle since a project with none of that
        # filled in would just show a row of dashes.
        #

        rack_header = QHBoxLayout()

        rack_title = QLabel("Rack Sizing")
        rack_title_font = rack_title.font()
        rack_title_font.setBold(True)
        rack_title_font.setPointSize(16)
        rack_title.setFont(rack_title_font)
        rack_header.addWidget(rack_title)

        rack_header.addStretch()

        self.rack_toggle_button = QPushButton("Show Rack Sizing")
        self.rack_toggle_button.setCheckable(True)
        self.rack_toggle_button.toggled.connect(self._on_rack_toggle)
        rack_header.addWidget(self.rack_toggle_button)

        layout.addLayout(rack_header)

        self.rack_cards_widget = QWidget()
        rack_grid = QGridLayout(self.rack_cards_widget)

        self.card_primary_rack_units = SummaryWidget("Primary Rack Units", "-", compact=True)
        self.card_primary_power = SummaryWidget("Primary Power (W)", "-", compact=True)
        self.card_dr_rack_units = SummaryWidget("DR Rack Units", "-", compact=True)
        self.card_dr_power = SummaryWidget("DR Power (W)", "-", compact=True)

        rack_cards = [
            self.card_primary_rack_units, self.card_primary_power,
            self.card_dr_rack_units, self.card_dr_power,
        ]
        for i, card in enumerate(rack_cards):
            rack_grid.addWidget(card, 0, i)

        self.rack_cards_widget.setVisible(False)
        layout.addWidget(self.rack_cards_widget)

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

    def _on_dr_failover_toggle(self, checked: bool):
        self.dr_failover_toggle_button.setText("Show Current DR" if checked else "Preview DR Failover")
        self.dr_failover_note_label.setVisible(checked)
        self.refresh()

    def _on_rack_toggle(self, checked: bool):
        self.rack_cards_widget.setVisible(checked)
        self.rack_toggle_button.setText("Hide Rack Sizing" if checked else "Show Rack Sizing")

    @staticmethod
    def _format_watts(watts: float) -> str:
        if not watts:
            return "-"
        if watts >= 1000:
            return f"{watts / 1000:.2f} kW"
        return f"{watts:.0f} W"

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
        if self.dr_failover_toggle_button.isChecked():
            self.dr_card.set_report(build_dr_failover_report(project, thresholds))
        else:
            self.dr_card.set_report(dr_report)

        #
        # Rack sizing
        #

        primary_rack = compute_rack_sizing(project, PRIMARY)
        dr_rack = compute_rack_sizing(project, DR)

        if primary_rack.is_cloud:
            self.card_primary_rack_units.set_value("Cloud")
            self.card_primary_power.set_value("Cloud")
        else:
            self.card_primary_rack_units.set_value(f"{primary_rack.rack_units} U" if primary_rack.rack_units else "-")
            self.card_primary_power.set_value(self._format_watts(primary_rack.power_watts))

        if dr_rack.is_cloud:
            self.card_dr_rack_units.set_value("Cloud")
            self.card_dr_power.set_value("Cloud")
        else:
            self.card_dr_rack_units.set_value(f"{dr_rack.rack_units} U" if dr_rack.rack_units else "-")
            self.card_dr_power.set_value(self._format_watts(dr_rack.power_watts))

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
