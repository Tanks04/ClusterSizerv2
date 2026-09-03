from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.calculations.sizing import build_reports, build_failover_scenario_report, build_failover_report
from src.calculations.rack import compute_rack_sizing
from src.calculations.attention import compute_attention_items
from src.services.project_service import ProjectService

from src.gui.widgets.site_capacity_widget import SiteCapacityWidget
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.attention_panel import AttentionPanel


class SummaryPage(QWidget):
    """Combined overview: a compact top-line card row (formerly its own
    Dashboard tab - merged in here since it's the same "quick glance at
    the whole project" purpose as the detailed view below it, just one
    tab instead of two) followed by a per-site deep-dive (capacity,
    demand, oversubscription, N+1, and failover-assignment readiness),
    one card per site in the project - not a fixed Primary/DR pair.
    This is the page that answers "do I have enough resources?"."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.site_cards: dict[str, SiteCapacityWidget] = {}
        self.rack_cards: dict[str, tuple[SummaryWidget, SummaryWidget]] = {}

        self._create_ui()

        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        # The page can grow taller than the window once there's a real
        # Attention Needed list (or just enough project data generally) -
        # same fix already applied to the entity dialogs for the same
        # reason: without this, content past the bottom of the window is
        # simply unreachable, no scrollbar, no way to resize around it.
        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

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
        self.card_sites = SummaryWidget("Sites", "0", compact=True)

        top_cards = [
            self.card_servers, self.card_cores, self.card_ram,
            self.card_storage, self.card_vms, self.card_sites,
        ]
        for i, card in enumerate(top_cards):
            top_grid.addWidget(card, i // 4, i % 4)

        #
        # Deep-dive: one card per site (was a fixed Primary/DR pair) -
        # laid out 2 per row, so Primary/DR still land side by side as
        # before, with any additional sites forming further rows below
        # in the same size/style, rather than a special case.
        #

        summary_header = QHBoxLayout()

        summary_title = QLabel("Cluster Summary")
        summary_title_font = summary_title.font()
        summary_title_font.setBold(True)
        summary_title_font.setPointSize(16)
        summary_title.setFont(summary_title_font)
        summary_header.addWidget(summary_title)

        summary_header.addStretch()

        self.failover_preview_toggle_button = QPushButton("Preview Failover")
        self.failover_preview_toggle_button.setCheckable(True)
        self.failover_preview_toggle_button.setToolTip(
            "Shows each site as if its assigned failover VMs were activated "
            "there right now - same hardware, added demand."
        )
        self.failover_preview_toggle_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #fb8c00; color: white; font-weight: bold;"
            "   padding: 4px 14px; border-radius: 4px; border: none;"
            "}"
            "QPushButton:hover { background-color: #f57c00; }"
            "QPushButton:checked { background-color: #e65100; }"
        )
        self.failover_preview_toggle_button.toggled.connect(self._on_failover_preview_toggle)
        summary_header.addWidget(self.failover_preview_toggle_button)

        layout.addLayout(summary_header)

        self.sites_grid = QGridLayout()
        layout.addLayout(self.sites_grid)

        self.failover_preview_note_label = QLabel(
            "\u26a0 Showing the FAILOVER scenario for every site - live load + "
            "assigned failover VMs' footprint, not what's actually running today."
        )
        self.failover_preview_note_label.setStyleSheet("color: #ed6c02; font-weight: bold;")
        self.failover_preview_note_label.setWordWrap(True)
        self.failover_preview_note_label.setVisible(False)
        layout.addWidget(self.failover_preview_note_label)

        #
        # Rack sizing - optional, only meaningful once someone has
        # entered Rack Size/Power on at least some equipment. Hidden by
        # default behind a toggle since a project with none of that
        # filled in would just show a row of dashes. One pair of cards
        # per site, same 2-per-row layout as the site cards above.
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
        self.rack_toggle_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #8bc34a; color: #1b2e0a; font-weight: bold;"
            "   padding: 4px 14px; border-radius: 4px; border: none;"
            "}"
            "QPushButton:hover { background-color: #7cb342; }"
            "QPushButton:checked { background-color: #558b2f; color: white; }"
        )
        self.rack_toggle_button.toggled.connect(self._on_rack_toggle)
        rack_header.addWidget(self.rack_toggle_button)

        layout.addLayout(rack_header)

        self.rack_cards_widget = QWidget()
        self.rack_grid = QGridLayout(self.rack_cards_widget)

        self.rack_cards_widget.setVisible(False)
        layout.addWidget(self.rack_cards_widget)

        #
        # Attention Needed - everything else on this page (and a couple
        # of things from other tabs: Backup compliance, Maintenance
        # expiry) that's Warning/Critical, in one place.
        #

        self.attention_panel = AttentionPanel()
        layout.addWidget(self.attention_panel)

        layout.addStretch()

    def _on_failover_preview_toggle(self, checked: bool):
        self.failover_preview_toggle_button.setText("Show Current Load" if checked else "Preview Failover")
        self.failover_preview_note_label.setVisible(checked)
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

    @staticmethod
    def _format_rack_units(rack) -> str:
        if not rack.rack_units:
            return "-"
        if not rack.capacity_u:
            return f"{rack.rack_units} U"
        marker = "\u26a0 " if rack.over_capacity else ""
        return f"{marker}{rack.rack_units} / {rack.capacity_u} U"

    def _ensure_site_cards(self, site_names: list[str]) -> None:
        """Rebuilds the site-card grids only when the site LIST itself
        has changed (added/removed) - cheap early exit on every other
        refresh, which just updates values on the existing widgets."""
        if set(self.site_cards.keys()) == set(site_names):
            return

        for widget in self.site_cards.values():
            widget.setParent(None)
            widget.deleteLater()
        self.site_cards.clear()

        for widgets in self.rack_cards.values():
            for w in widgets:
                w.setParent(None)
                w.deleteLater()
        self.rack_cards.clear()

        for i, site in enumerate(site_names):
            card = SiteCapacityWidget(site)
            self.site_cards[site] = card
            self.sites_grid.addWidget(card, i // 2, i % 2)

            units_card = SummaryWidget(f"{site} Rack Units", "-", compact=True)
            power_card = SummaryWidget(f"{site} Power (W)", "-", compact=True)
            self.rack_cards[site] = (units_card, power_card)
            self.rack_grid.addWidget(units_card, i // 2, (i % 2) * 2)
            self.rack_grid.addWidget(power_card, i // 2, (i % 2) * 2 + 1)

    def refresh(self):
        project = self.service.project
        thresholds = self.service.thresholds

        #
        # Top-line cards
        #

        self.title_label.setText(project.name or "ClusterSizer")

        self.card_servers.set_value(project.server_count)
        self.card_cores.set_value(project.total_cores)
        self.card_ram.set_value(f"{project.total_ram} GB")

        total_storage_tb = sum(
            project.usable_storage_gb(site) for site in project.site_names
        ) / 1024
        self.card_storage.set_value(f"{total_storage_tb:.1f} TB")

        self.card_vms.set_value(len(project.vms))
        self.card_sites.set_value(len(project.site_names))

        #
        # Deep-dive: one card per site
        #

        self._ensure_site_cards(project.site_names)

        preview = self.failover_preview_toggle_button.isChecked()
        reports = build_reports(project, thresholds)

        for site in project.site_names:
            card = self.site_cards[site]
            if preview:
                card.set_report(build_failover_scenario_report(project, site, thresholds))
            else:
                card.set_report(reports[site])
            card.set_failover_report(build_failover_report(project, site, thresholds))

            rack = compute_rack_sizing(project, site)
            units_card, power_card = self.rack_cards[site]
            if rack.is_cloud:
                units_card.set_value("Cloud")
                power_card.set_value("Cloud")
            else:
                units_card.set_value(self._format_rack_units(rack))
                power_card.set_value(self._format_watts(rack.power_watts))

        self.attention_panel.set_items(compute_attention_items(project, thresholds))
