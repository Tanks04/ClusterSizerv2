from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.models.cluster import Cluster


class ClusterDialog(QDialog):

    def __init__(self, cluster: Cluster | None = None, sites: list | None = None,
                 default_color: str = "#64b5f6", parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cluster")
        self.resize(400, 280)
        self._color = default_color

        layout = QFormLayout(self)

        info = QPlainTextEdit(
            "An isolated compute failure domain (a vSphere Cluster, a Nutanix "
            "cluster, a Proxmox cluster, one of several independent Hyper-V "
            "Failover Clusters) - a site can host several of these side by side. "
            "Assign servers/VMs to this on their own dialogs."
        )
        info.setReadOnly(True)
        info.setFixedHeight(70)
        layout.addRow(info)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Cluster-A, vSAN-Prod-01...")
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(sites or ["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._pick_color)
        layout.addRow("Color", self.color_button)
        self._update_color_button()

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(60)
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._uid = None

        if cluster is not None:
            self.load(cluster)

    def _update_color_button(self) -> None:
        self.color_button.setText(self._color)
        self.color_button.setStyleSheet(
            f"background-color: {self._color}; color: white; font-weight: bold;"
        )

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, "Cluster Color")
        if chosen.isValid():
            self._color = chosen.name()
            self._update_color_button()

    def load(self, cluster: Cluster) -> None:
        self._uid = cluster.uid
        self.name_edit.setText(cluster.name)
        self.site_combo.setCurrentText(cluster.site)
        self._color = cluster.color
        self._update_color_button()
        self.notes_edit.setPlainText(cluster.notes)

    def get_cluster(self) -> Cluster:
        cluster = Cluster.create_default()

        if self._uid:
            cluster.uid = self._uid

        cluster.name = self.name_edit.text()
        cluster.site = self.site_combo.currentText()
        cluster.color = self._color
        cluster.notes = self.notes_edit.toPlainText()

        return cluster
