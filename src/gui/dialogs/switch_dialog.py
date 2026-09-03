from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.models.network_switch import REDUNDANCY_ROLES, SWITCH_TYPES, NetworkSwitch


class SwitchDialog(QDialog):

    def __init__(self, switch: NetworkSwitch | None = None, sites: list | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Network Device")
        self.resize(400, 420)

        # See ServerDialog for why this is scrollable.
        dialog_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QFormLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        dialog_layout.addWidget(scroll_area)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(sites or ["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vendor_edit = QLineEdit()
        layout.addRow("Vendor", self.vendor_edit)

        self.model_edit = QLineEdit()
        layout.addRow("Model", self.model_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(SWITCH_TYPES)
        layout.addRow("Type", self.type_combo)

        self.redundancy_group_edit = QLineEdit()
        self.redundancy_group_edit.setPlaceholderText("e.g. core-pair-01, fw-ha-01... (optional)")
        self.redundancy_group_edit.setToolTip(
            "Shared tag linking devices into one redundant set (HSRP pair, "
            "HA pair, MLAG stack) - same tag gets the same colored border."
        )
        layout.addRow("Redundancy Group", self.redundancy_group_edit)

        self.redundancy_role_combo = QComboBox()
        self.redundancy_role_combo.addItem("(none)", userData="")
        for role in REDUNDANCY_ROLES[1:]:
            self.redundancy_role_combo.addItem(role, userData=role)
        self.redundancy_role_combo.setToolTip(
            "Your own call, never auto-detected. Active/Standby = Cisco HSRP/"
            "VRRP; Active/Passive = firewall HA; Member = MLAG/stacking."
        )
        layout.addRow("Redundancy Role", self.redundancy_role_combo)

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

        self.rack_units_spin = QSpinBox()
        self.rack_units_spin.setRange(0, 60)
        self.rack_units_spin.setSuffix(" U")
        self.rack_units_spin.setSpecialValueText("(not set)")
        layout.addRow("Rack Size", self.rack_units_spin)

        self.power_watts_spin = QDoubleSpinBox()
        self.power_watts_spin.setRange(0.0, 20000.0)
        self.power_watts_spin.setSuffix(" W")
        self.power_watts_spin.setSpecialValueText("(not set)")
        self.power_watts_spin.setToolTip(
            "Use the nameplate/max draw from the datasheet, not \"typical\" - "
            "safer for circuit/PDU capacity planning."
        )
        layout.addRow("Power Consumption", self.power_watts_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 10_000_000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setSuffix(" EUR")
        self.price_spin.setSpecialValueText("(not set)")
        layout.addRow("Price", self.price_spin)

        self.notes_edit = QLineEdit()
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        dialog_layout.addWidget(buttons)

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
        self.redundancy_group_edit.setText(switch.redundancy_group)
        role_index = self.redundancy_role_combo.findData(switch.redundancy_role)
        self.redundancy_role_combo.setCurrentIndex(role_index if role_index >= 0 else 0)
        self.ports_1g_spin.setValue(switch.ports_1g)
        self.ports_10g_spin.setValue(switch.ports_10g)
        self.ports_25g_spin.setValue(switch.ports_25g)
        self.ports_40g_spin.setValue(switch.ports_40g)
        self.ports_100g_spin.setValue(switch.ports_100g)
        self.ports_fc_spin.setValue(switch.ports_fc)
        self.rack_units_spin.setValue(switch.rack_units)
        self.power_watts_spin.setValue(switch.power_watts)
        self.price_spin.setValue(switch.price)
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
        switch.redundancy_group = self.redundancy_group_edit.text()
        switch.redundancy_role = self.redundancy_role_combo.currentData() or ""
        switch.ports_1g = self.ports_1g_spin.value()
        switch.ports_10g = self.ports_10g_spin.value()
        switch.ports_25g = self.ports_25g_spin.value()
        switch.ports_40g = self.ports_40g_spin.value()
        switch.ports_100g = self.ports_100g_spin.value()
        switch.ports_fc = self.ports_fc_spin.value()
        switch.rack_units = self.rack_units_spin.value()
        switch.power_watts = self.power_watts_spin.value()
        switch.price = self.price_spin.value()
        switch.notes = self.notes_edit.text()

        return switch
