from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from src.models.cluster_project import ClusterProject
from src.models.network_connection import (
    NetworkConnection,
    SPEED_OPTIONS,
    MEDIA_OPTIONS,
    PURPOSE_OPTIONS,
)
from src.calculations.networking import server_nic_usage, switch_port_usage, format_usage


class ConnectionDialog(QDialog):
    """Server <-> Switch connection. Dropdowns are populated from the current
    project; below each one, free/used for the selected speed is shown,
    purely informational (doesn't block saving if oversubscribed - see the
    note in calculations/networking.py)."""

    def __init__(
        self,
        project: ClusterProject,
        connection: NetworkConnection | None = None,
        exclude_uid: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.project = project
        self._exclude_uid = exclude_uid

        self.setWindowTitle("Network Connection")
        self.resize(420, 300)

        layout = QFormLayout(self)

        self.server_combo = QComboBox()
        for server in project.servers:
            self.server_combo.addItem(server.name or "(unnamed)", server.uid)
        layout.addRow("Server", self.server_combo)

        self.switch_combo = QComboBox()
        for switch in project.switches:
            self.switch_combo.addItem(switch.name or "(unnamed)", switch.uid)
        layout.addRow("Switch", self.switch_combo)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(SPEED_OPTIONS)
        layout.addRow("Speed", self.speed_combo)

        self.media_combo = QComboBox()
        self.media_combo.addItems(MEDIA_OPTIONS)
        layout.addRow("Media", self.media_combo)

        self.port_label_edit = QLineEdit()
        self.port_label_edit.setPlaceholderText("e.g. Gi1/0/3, Uplink #1 (optional)")
        layout.addRow("Switch Port Label", self.port_label_edit)

        self.purpose_combo = QComboBox()
        self.purpose_combo.addItems(PURPOSE_OPTIONS)
        layout.addRow("Purpose", self.purpose_combo)

        self.notes_edit = QLineEdit()
        layout.addRow("Notes", self.notes_edit)

        self.usage_label = QLabel("-")
        self.usage_label.setWordWrap(True)
        layout.addRow("Current port status", self.usage_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.server_combo.currentIndexChanged.connect(self._update_usage_hint)
        self.switch_combo.currentIndexChanged.connect(self._update_usage_hint)
        self.speed_combo.currentIndexChanged.connect(self._update_usage_hint)

        self._uid = None

        if connection is not None:
            self.load(connection)

        self._update_usage_hint()

    def _update_usage_hint(self) -> None:
        if not self.project.servers or not self.project.switches:
            self.usage_label.setText("Add at least one server and one switch.")
            return

        server_uid = self.server_combo.currentData()
        switch_uid = self.switch_combo.currentData()
        speed = self.speed_combo.currentText()

        # Exclude the connection currently being edited from the calc, so it doesn't count itself
        connections = [c for c in self.project.connections if c.uid != self._exclude_uid]

        server = next((s for s in self.project.servers if s.uid == server_uid), None)
        switch = next((s for s in self.project.switches if s.uid == switch_uid), None)

        parts = []

        if server:
            server_usage = [
                u for u in server_nic_usage(server, connections) if u.speed == speed
            ]
            if server_usage:
                u = server_usage[0]
                parts.append(f"Server {speed}: {u.used}/{u.total} used")
            else:
                parts.append(f"Server has no declared {speed} NICs (Servers tab)")

        if switch:
            switch_usage = [
                u for u in switch_port_usage(switch, connections) if u.speed == speed
            ]
            if switch_usage:
                u = switch_usage[0]
                parts.append(f"Switch {speed}: {u.used}/{u.total} used")
            else:
                parts.append(f"Switch has no declared {speed} ports")

        self.usage_label.setText("  |  ".join(parts) if parts else "-")

    def load(self, connection: NetworkConnection) -> None:
        self._uid = connection.uid

        idx = self.server_combo.findData(connection.server_uid)
        if idx >= 0:
            self.server_combo.setCurrentIndex(idx)

        idx = self.switch_combo.findData(connection.switch_uid)
        if idx >= 0:
            self.switch_combo.setCurrentIndex(idx)

        self.speed_combo.setCurrentText(connection.speed)
        self.media_combo.setCurrentText(connection.media)
        self.port_label_edit.setText(connection.switch_port_label)
        self.purpose_combo.setCurrentText(connection.purpose)
        self.notes_edit.setText(connection.notes)

    def get_connection(self) -> NetworkConnection:
        connection = NetworkConnection.create_default()

        if self._uid:
            connection.uid = self._uid

        connection.server_uid = self.server_combo.currentData() or ""
        connection.switch_uid = self.switch_combo.currentData() or ""
        connection.speed = self.speed_combo.currentText()
        connection.media = self.media_combo.currentText()
        connection.switch_port_label = self.port_label_edit.text()
        connection.purpose = self.purpose_combo.currentText()
        connection.notes = self.notes_edit.text()

        return connection
