from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)

from src.models.network_switch import NetworkSwitch


class SwitchDialog(QDialog):

    def __init__(self, switch: NetworkSwitch | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Network Switch")
        self.resize(400, 420)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vendor_edit = QLineEdit()
        layout.addRow("Vendor", self.vendor_edit)

        self.model_edit = QLineEdit()
        layout.addRow("Model", self.model_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["LAN", "SAN/FC", "Unified"])
        layout.addRow("Type", self.type_combo)

        self.ports_1g_spin = QSpinBox()
        self.ports_1g_spin.setRange(0, 512)
        self.ports_1g_spin.setValue(48)
        layout.addRow("Ports 1G (RJ45)", self.ports_1g_spin)

        self.ports_10g_spin = QSpinBox()
        self.ports_10g_spin.setRange(0, 512)
        layout.addRow("Ports 10G (SFP+/RJ45)", self.ports_10g_spin)

        self.ports_25g_spin = QSpinBox()
        self.ports_25g_spin.setRange(0, 512)
        self.ports_25g_spin.setValue(4)
        layout.addRow("Ports 25G (SFP28)", self.ports_25g_spin)

        self.ports_40g_spin = QSpinBox()
        self.ports_40g_spin.setRange(0, 512)
        layout.addRow("Ports 40G (QSFP+)", self.ports_40g_spin)

        self.ports_100g_spin = QSpinBox()
        self.ports_100g_spin.setRange(0, 512)
        layout.addRow("Ports 100G (QSFP28)", self.ports_100g_spin)

        self.ports_fc_spin = QSpinBox()
        self.ports_fc_spin.setRange(0, 512)
        layout.addRow("Ports FC", self.ports_fc_spin)

        self.notes_edit = QLineEdit()
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._uid = None

        if switch is not None:
            self.load(switch)

    def load(self, switch: NetworkSwitch) -> None:
        self._uid = switch.uid
        self.name_edit.setText(switch.name)
        self.site_combo.setCurrentText(switch.site)
        self.vendor_edit.setText(switch.vendor)
        self.model_edit.setText(switch.model)
        self.type_combo.setCurrentText(switch.switch_type)
        self.ports_1g_spin.setValue(switch.ports_1g)
        self.ports_10g_spin.setValue(switch.ports_10g)
        self.ports_25g_spin.setValue(switch.ports_25g)
        self.ports_40g_spin.setValue(switch.ports_40g)
        self.ports_100g_spin.setValue(switch.ports_100g)
        self.ports_fc_spin.setValue(switch.ports_fc)
        self.notes_edit.setText(switch.notes)

    def get_switch(self) -> NetworkSwitch:
        switch = NetworkSwitch.create_default()

        if self._uid:
            switch.uid = self._uid

        switch.name = self.name_edit.text()
        switch.site = self.site_combo.currentText()
        switch.vendor = self.vendor_edit.text()
        switch.model = self.model_edit.text()
        switch.switch_type = self.type_combo.currentText()
        switch.ports_1g = self.ports_1g_spin.value()
        switch.ports_10g = self.ports_10g_spin.value()
        switch.ports_25g = self.ports_25g_spin.value()
        switch.ports_40g = self.ports_40g_spin.value()
        switch.ports_100g = self.ports_100g_spin.value()
        switch.ports_fc = self.ports_fc_spin.value()
        switch.notes = self.notes_edit.text()

        return switch
