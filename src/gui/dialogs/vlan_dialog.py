from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from src.models.vlan import Vlan


class VlanDialog(QDialog):

    def __init__(self, vlan: Vlan | None = None, sites: list | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("VLAN")
        self.resize(400, 320)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. DMZ, Management, VLAN 10...")
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(sites or ["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.network_edit = QLineEdit()
        self.network_edit.setPlaceholderText("e.g. 192.168.10.0/24")
        layout.addRow("Network", self.network_edit)

        self.gateway_edit = QLineEdit()
        self.gateway_edit.setPlaceholderText("e.g. 192.168.10.1")
        layout.addRow("Gateway", self.gateway_edit)

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

        if vlan is not None:
            self.load(vlan)

    def load(self, vlan: Vlan) -> None:
        self._uid = vlan.uid
        self.name_edit.setText(vlan.name)
        self.site_combo.setCurrentText(vlan.site)
        self.network_edit.setText(vlan.network)
        self.gateway_edit.setText(vlan.gateway)
        self.notes_edit.setPlainText(vlan.notes)

    def get_vlan(self) -> Vlan:
        vlan = Vlan.create_default()

        if self._uid:
            vlan.uid = self._uid

        vlan.name = self.name_edit.text()
        vlan.site = self.site_combo.currentText()
        vlan.network = self.network_edit.text()
        vlan.gateway = self.gateway_edit.text()
        vlan.notes = self.notes_edit.toPlainText()

        return vlan
