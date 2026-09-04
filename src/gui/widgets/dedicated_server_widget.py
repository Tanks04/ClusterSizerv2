from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.server import Server


class DedicatedServerWidget(QGroupBox):
    """One 2-line block per server that has VMs pinned directly to it
    (Server, not Cluster) - "how loaded would this ONE host be from
    just its own dedicated VMs", independent of whatever the parent
    Cluster (if any) looks like overall. Hidden entirely when no
    server has any pinned VMs - most projects never use this."""

    def __init__(self, parent=None):
        super().__init__("Dedicated Server Loads", parent)
        self._layout = QVBoxLayout(self)
        self._labels: list[QLabel] = []

    def set_data(self, project: ClusterProject, thresholds: Thresholds) -> None:
        for label in self._labels:
            label.deleteLater()
        self._labels.clear()

        pinned_servers = [
            s for s in project.servers if project.pinned_vms_for_server(s.uid)
        ]
        self.setVisible(bool(pinned_servers))
        if not pinned_servers:
            return

        for server in pinned_servers:
            self._add_server_block(project, thresholds, server)

    def _add_server_block(self, project: ClusterProject, thresholds: Thresholds, server: Server) -> None:
        vms = project.pinned_vms_for_server(server.uid)
        vcpu = project.server_vcpu_demand(server.uid)
        ram = project.server_ram_demand_gb(server.uid)
        disk = project.server_disk_demand_gb(server.uid)
        cpu_ratio = project.server_cpu_ratio(server)
        ram_ratio = project.server_ram_ratio(server)

        spec_line = f"{server.sockets}x{server.cores_per_socket}c, {server.ram_gb} GB RAM"
        header = QLabel(f"<b>{server.name} has dedicated VMs.</b> {spec_line}")
        header.setWordWrap(True)
        self._layout.addWidget(header)
        self._labels.append(header)

        cpu_text = f"{cpu_ratio:.1f}:1" if cpu_ratio is not None else "n/a"
        ram_text = f"{ram_ratio * 100:.0f}%" if ram_ratio is not None else "n/a"
        cpu_status = thresholds.cpu_status(cpu_ratio) if cpu_ratio is not None else None
        ram_status = thresholds.ram_status(ram_ratio) if ram_ratio is not None else None
        cpu_marker = "\u26a0 " if cpu_status is not None and cpu_status.value in ("Warning", "Critical") else ""
        ram_marker = "\u26a0 " if ram_status is not None and ram_status.value in ("Warning", "Critical") else ""

        detail = QLabel(
            f"{len(vms)}x VM's, {ram:.0f} GB RAM, {disk:.0f} GB disk: "
            f"CPU-OS: {cpu_marker}{cpu_text}  RAM-UTIL: {ram_marker}{ram_text}"
        )
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #555;")
        self._layout.addWidget(detail)
        self._labels.append(detail)
