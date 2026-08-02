from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
)

from src.models.server import Server


class ServerDialog(QDialog):

    def __init__(self, server: Server | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Server")

        self.resize(440, 620)

        outer = QVBoxLayout(self)

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

        self.core_spin.setValue(16)

        layout.addRow("Cores / Socket", self.core_spin)

        #
        # Threads per core
        #

        self.threads_spin = QSpinBox()

        self.threads_spin.setRange(1, 4)

        self.threads_spin.setValue(2)

        self.threads_spin.setToolTip(
            "2 = Hyper-Threading/SMT uključen, 1 = isključen"
        )

        layout.addRow("Threads / Core", self.threads_spin)

        #
        # RAM
        #

        self.ram_spin = QSpinBox()

        self.ram_spin.setRange(1, 32768)

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

        outer.addWidget(nic_box)

        #
        # Batch count - samo kod dodavanja novog servera. Serveri u istom
        # clusteru su gotovo uvijek identični pa nema smisla tipkati N puta.
        #

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 64)
        self.count_spin.setValue(1)
        self.count_spin.setToolTip(
            "Napravi N identičnih servera odjednom. Imena se auto-numeriraju "
            "(npr. 'esxi' -> esxi-01, esxi-02, ...)."
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

        outer.addWidget(buttons)

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

        self.ram_spin.setValue(server.ram_gb)

        self.freq_spin.setValue(server.cpu_frequency)

        self.warranty_edit.setText(server.warranty_expiry)

        self.nic_1g_spin.setValue(server.nic_1g)
        self.nic_10g_spin.setValue(server.nic_10g)
        self.nic_25g_spin.setValue(server.nic_25g)
        self.nic_40g_spin.setValue(server.nic_40g)
        self.nic_100g_spin.setValue(server.nic_100g)
        self.nic_fc_spin.setValue(server.nic_fc)

    def _fill_common(self, server: Server) -> None:
        server.site = self.site_combo.currentText()
        server.vendor = self.vendor_edit.text()
        server.model = self.model_edit.text()
        server.cpu_vendor = self.cpu_vendor_combo.currentText()
        server.cpu_model = self.cpu_edit.text()
        server.sockets = self.socket_spin.value()
        server.cores_per_socket = self.core_spin.value()
        server.threads_per_core = self.threads_spin.value()
        server.ram_gb = self.ram_spin.value()
        server.cpu_frequency = self.freq_spin.value()
        server.warranty_expiry = self.warranty_edit.text()
        server.nic_1g = self.nic_1g_spin.value()
        server.nic_10g = self.nic_10g_spin.value()
        server.nic_25g = self.nic_25g_spin.value()
        server.nic_40g = self.nic_40g_spin.value()
        server.nic_100g = self.nic_100g_spin.value()
        server.nic_fc = self.nic_fc_spin.value()

    def get_server(self) -> Server:
        """Za Edit mod (jedan server)."""
        server = Server.create_default()

        if self._uid:
            server.uid = self._uid

        server.name = self.name_edit.text()
        self._fill_common(server)

        return server

    def get_servers(self) -> list[Server]:
        """Za Add mod - vraća 1..N servera (batch), auto-numeriranih ako je
        count > 1 i ako je uneseno ime."""
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
