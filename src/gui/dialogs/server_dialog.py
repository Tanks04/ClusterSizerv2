from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.models.server import Server


class ServerDialog(QDialog):

    def __init__(self, server: Server | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Server")

        self.resize(440, 620)

        # The dialog kept growing past the screen's height as fields were
        # added over time, with no way to reach the bottom (no scrollbar,
        # and the bottom edge could end up off-screen so it couldn't be
        # dragged either). Fix: the form goes in a scroll area; only the
        # OK/Cancel buttons live outside it, so they're always reachable
        # regardless of how tall the form itself grows.
        dialog_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        outer = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        dialog_layout.addWidget(scroll_area)

        layout = QFormLayout()
        outer.addLayout(layout)

        #
        # Name
        #

        self.name_edit = QLineEdit()

        layout.addRow("Name", self.name_edit)

        #
        # Site
        #

        self.site_combo = QComboBox()

        self.site_combo.addItems(
            [
                "Primary",
                "DR",
            ]
        )

        layout.addRow("Site", self.site_combo)

        #
        # Vendor
        #

        self.vendor_edit = QLineEdit()

        layout.addRow("Vendor", self.vendor_edit)

        #
        # Model
        #

        self.model_edit = QLineEdit()

        layout.addRow("Model", self.model_edit)

        #
        # CPU vendor
        #

        self.cpu_vendor_combo = QComboBox()

        self.cpu_vendor_combo.addItems(
            [
                "Intel",
                "AMD",
                "Other",
            ]
        )

        layout.addRow("CPU Vendor", self.cpu_vendor_combo)

        #
        # CPU model
        #

        self.cpu_edit = QLineEdit()

        layout.addRow("CPU Model", self.cpu_edit)

        #
        # Sockets
        #

        self.socket_spin = QSpinBox()

        self.socket_spin.setRange(1, 8)

        self.socket_spin.setValue(2)

        layout.addRow("Sockets", self.socket_spin)

        #
        # Cores per socket
        #

        self.core_spin = QSpinBox()

        self.core_spin.setRange(1, 256)
        self.core_spin.setSingleStep(2)  # cores per socket are always even

        self.core_spin.setValue(16)

        layout.addRow("Cores / Socket", self.core_spin)

        #
        # Threads per core
        #

        self.threads_spin = QSpinBox()

        self.threads_spin.setRange(1, 4)

        self.threads_spin.setValue(2)

        self.threads_spin.setToolTip(
            "SMT width - 2 for typical x86 Hyper-Threading. Only counted "
            "toward CPU capacity if 'Hyperthreading Enabled' below is checked."
        )

        layout.addRow("Threads / Core", self.threads_spin)

        #
        # Hyperthreading gate - affects CPU oversubscription math directly:
        # when off, this server contributes physical cores only, not
        # threads, regardless of the Threads/Core value above.
        #

        self.ht_check = QCheckBox("Hyperthreading Enabled")
        self.ht_check.setChecked(True)
        self.ht_check.setToolTip(
            "When checked, this server's effective CPU capacity for "
            "oversubscription math is cores \u00d7 threads/core. When "
            "unchecked, it's physical cores only - Threads/Core is ignored "
            "(but kept, in case you re-enable HT later)."
        )
        self.ht_check.toggled.connect(self.threads_spin.setEnabled)
        layout.addRow("", self.ht_check)

        #
        # RAM
        #

        self.ram_spin = QSpinBox()

        self.ram_spin.setRange(1, 32768)
        self.ram_spin.setSingleStep(1024)  # common DIMM-friendly increment

        self.ram_spin.setSuffix(" GB")

        self.ram_spin.setValue(256)

        layout.addRow("RAM", self.ram_spin)

        #
        # CPU Frequency
        #

        self.freq_spin = QDoubleSpinBox()

        self.freq_spin.setDecimals(2)

        self.freq_spin.setRange(1.0, 6.0)

        self.freq_spin.setSingleStep(0.1)

        self.freq_spin.setSuffix(" GHz")

        self.freq_spin.setValue(2.5)

        layout.addRow("CPU Frequency", self.freq_spin)

        #
        # Warranty expiry
        #

        self.warranty_edit = QLineEdit()

        self.warranty_edit.setPlaceholderText("npr. 2027-05-01")

        layout.addRow("Warranty Expiry", self.warranty_edit)

        self.ip_address_edit = QLineEdit()
        self.ip_address_edit.setPlaceholderText("e.g. 10.88.1.10 (management or primary IP)")
        layout.addRow("IP Address", self.ip_address_edit)

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

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(60)
        layout.addRow("Notes", self.notes_edit)

        #
        # NIC inventory (Network tab koristi ovo za slobodno/zauzeto)
        #

        nic_box = QGroupBox("Network NICs (opcionalno)")
        nic_form = QFormLayout(nic_box)

        self.nic_1g_spin = QSpinBox()
        self.nic_1g_spin.setRange(0, 64)
        self.nic_1g_spin.setValue(2)
        nic_form.addRow("1G (RJ45)", self.nic_1g_spin)

        self.nic_10g_spin = QSpinBox()
        self.nic_10g_spin.setRange(0, 64)
        nic_form.addRow("10G (SFP+/RJ45)", self.nic_10g_spin)

        self.nic_25g_spin = QSpinBox()
        self.nic_25g_spin.setRange(0, 64)
        self.nic_25g_spin.setValue(2)
        nic_form.addRow("25G (SFP28)", self.nic_25g_spin)

        self.nic_40g_spin = QSpinBox()
        self.nic_40g_spin.setRange(0, 64)
        nic_form.addRow("40G (QSFP+)", self.nic_40g_spin)

        self.nic_100g_spin = QSpinBox()
        self.nic_100g_spin.setRange(0, 64)
        nic_form.addRow("100G (QSFP28)", self.nic_100g_spin)

        self.nic_fc_spin = QSpinBox()
        self.nic_fc_spin.setRange(0, 64)
        nic_form.addRow("FC (HBA)", self.nic_fc_spin)

        self.nic_sas_spin = QSpinBox()
        self.nic_sas_spin.setRange(0, 64)
        self.nic_sas_spin.setToolTip(
            "Direct-attach SAS HBA ports - for servers wired straight to "
            "storage, no switch in between."
        )
        nic_form.addRow("SAS (direct-attach)", self.nic_sas_spin)

        outer.addWidget(nic_box)

        #
        # Batch count - only when adding a new server. Servers in the same
        # cluster are almost always identical, so no point typing N times.
        #

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 64)
        self.count_spin.setValue(1)
        self.count_spin.setToolTip(
            "Create N identical servers at once. Names are auto-numbered "
            "(e.g. 'esxi' -> esxi-01, esxi-02, ...)."
        )

        self.count_row_label = None

        if server is None:
            count_form = QFormLayout()
            count_form.addRow("Broj servera za kreirati", self.count_spin)
            outer.addLayout(count_form)

        #
        # Buttons
        #

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            |
            QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)

        buttons.rejected.connect(self.reject)

        dialog_layout.addWidget(buttons)

        #
        # Existing server
        #

        self._uid = None

        if server is not None:

            self.load(server)

    def load(self, server: Server) -> None:

        self._uid = server.uid

        self.name_edit.setText(server.name)

        self.site_combo.setCurrentText(server.site)

        self.vendor_edit.setText(server.vendor)

        self.model_edit.setText(server.model)

        if server.cpu_vendor:
            self.cpu_vendor_combo.setCurrentText(server.cpu_vendor)

        self.cpu_edit.setText(server.cpu_model)

        self.socket_spin.setValue(server.sockets)

        self.core_spin.setValue(server.cores_per_socket)

        self.threads_spin.setValue(server.threads_per_core)

        self.ht_check.setChecked(server.hyperthreading_enabled)
        self.threads_spin.setEnabled(server.hyperthreading_enabled)

        self.ram_spin.setValue(server.ram_gb)

        self.freq_spin.setValue(server.cpu_frequency)

        self.warranty_edit.setText(server.warranty_expiry)
        self.ip_address_edit.setText(server.ip_address)
        self.rack_units_spin.setValue(server.rack_units)
        self.power_watts_spin.setValue(server.power_watts)
        self.price_spin.setValue(server.price)
        self.notes_edit.setPlainText(server.notes)

        self.nic_1g_spin.setValue(server.nic_1g)
        self.nic_10g_spin.setValue(server.nic_10g)
        self.nic_25g_spin.setValue(server.nic_25g)
        self.nic_40g_spin.setValue(server.nic_40g)
        self.nic_100g_spin.setValue(server.nic_100g)
        self.nic_fc_spin.setValue(server.nic_fc)
        self.nic_sas_spin.setValue(server.nic_sas)

    def _fill_common(self, server: Server) -> None:
        server.site = self.site_combo.currentText()
        server.vendor = self.vendor_edit.text()
        server.model = self.model_edit.text()
        server.cpu_vendor = self.cpu_vendor_combo.currentText()
        server.cpu_model = self.cpu_edit.text()
        server.sockets = self.socket_spin.value()
        server.cores_per_socket = self.core_spin.value()
        server.threads_per_core = self.threads_spin.value()
        server.hyperthreading_enabled = self.ht_check.isChecked()
        server.ram_gb = self.ram_spin.value()
        server.cpu_frequency = self.freq_spin.value()
        server.warranty_expiry = self.warranty_edit.text()
        server.ip_address = self.ip_address_edit.text()
        server.rack_units = self.rack_units_spin.value()
        server.power_watts = self.power_watts_spin.value()
        server.price = self.price_spin.value()
        server.notes = self.notes_edit.toPlainText()
        server.nic_1g = self.nic_1g_spin.value()
        server.nic_10g = self.nic_10g_spin.value()
        server.nic_25g = self.nic_25g_spin.value()
        server.nic_40g = self.nic_40g_spin.value()
        server.nic_100g = self.nic_100g_spin.value()
        server.nic_fc = self.nic_fc_spin.value()
        server.nic_sas = self.nic_sas_spin.value()

    def get_server(self) -> Server:
        """For Edit mode (one server)."""
        server = Server.create_default()

        if self._uid:
            server.uid = self._uid

        server.name = self.name_edit.text()
        self._fill_common(server)

        return server

    def get_servers(self) -> list[Server]:
        """For Add mode - returns 1..N servers (batch), auto-numbered if
        count > 1 and a name was entered."""
        base_name = self.name_edit.text().strip()
        count = self.count_spin.value()

        servers = []
        for i in range(count):
            server = Server.create_default()
            if base_name and count > 1:
                server.name = f"{base_name}-{i + 1:02d}"
            else:
                server.name = base_name
            self._fill_common(server)
            servers.append(server)

        return servers
