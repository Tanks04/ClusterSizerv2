from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from src.services.project_service import ProjectService

from ..widgets.summary_widget import SummaryWidget


class DashboardPage(QWidget):
    """Landing page: quick overview of the whole project (both sites
    combined). For a detailed Primary/DR breakdown, see the Summary page."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()

        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        self.title_label = QLabel("ClusterSizer")
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(18)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Capacity planning for virtualized infrastructure")
        layout.addWidget(self.subtitle_label)

        grid = QGridLayout()
        layout.addLayout(grid)

        self.card_servers = SummaryWidget("Servers (Total)", "0")
        self.card_cores = SummaryWidget("Cores (Total)", "0")
        self.card_ram = SummaryWidget("RAM (Total)", "0 GB")
        self.card_storage = SummaryWidget("Usable Storage (Total)", "0 TB")
        self.card_vms = SummaryWidget("VMs (Total)", "0")
        self.card_primary_servers = SummaryWidget("Primary Servers", "0")
        self.card_dr_servers = SummaryWidget("DR Servers", "0")
        self.card_dr_ready = SummaryWidget("DR Ready", "-")

        cards = [
            self.card_servers, self.card_cores, self.card_ram, self.card_storage,
            self.card_vms, self.card_primary_servers, self.card_dr_servers, self.card_dr_ready,
        ]

        for i, card in enumerate(cards):
            grid.addWidget(card, i // 4, i % 4)

        layout.addStretch()

    def refresh(self):
        from src.models.cluster_project import PRIMARY, DR

        project = self.service.project

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
