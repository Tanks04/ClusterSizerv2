from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QDoubleSpinBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.models.storage import Storage, StorageShelf


class StorageDialog(QDialog):

    def __init__(self, storage: Storage | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Storage")

        self.resize(440, 560)

        outer = QVBoxLayout(self)
        layout = QFormLayout()
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vendor_edit = QLineEdit()
        layout.addRow("Vendor", self.vendor_edit)

        self.model_edit = QLineEdit()
        layout.addRow("Model", self.model_edit)

        self.raw_spin = QDoubleSpinBox()
        self.raw_spin.setDecimals(2)
        self.raw_spin.setRange(0.0, 100000.0)
        self.raw_spin.setSuffix(" TB")
        self.raw_spin.setValue(100.0)
        self.raw_spin.valueChanged.connect(self._recalc_overhead)
        layout.addRow("Raw Capacity", self.raw_spin)

        self.usable_spin = QDoubleSpinBox()
        self.usable_spin.setDecimals(2)
        self.usable_spin.setRange(0.0, 100000.0)
        self.usable_spin.setSuffix(" TB")
        self.usable_spin.setValue(80.0)
        self.usable_spin.valueChanged.connect(self._recalc_overhead)
        layout.addRow("Usable Capacity", self.usable_spin)

        self.overhead_spin = QDoubleSpinBox()
        self.overhead_spin.setDecimals(1)
        self.overhead_spin.setRange(0.0, 100.0)
        self.overhead_spin.setSuffix(" %")
        self.overhead_spin.setReadOnly(True)
        self.overhead_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.overhead_spin.setToolTip(
            "Calculated automatically from Raw/Usable (RAID, erasure coding, etc.)"
        )
        layout.addRow("RAID/EC Overhead", self.overhead_spin)

        #
        # Connectivity ports - same pattern as Server NICs / Switch ports.
        # Used on the Network tab for free/used tracking, including
        # direct-attach links straight to a server (no switch).
        #

        ports_box = QGroupBox("Connectivity Ports (optional)")
        ports_form = QFormLayout(ports_box)

        self.ports_1g_spin = QSpinBox()
        self.ports_1g_spin.setRange(0, 128)
        ports_form.addRow("1G (RJ45)", self.ports_1g_spin)

        self.ports_10g_spin = QSpinBox()
        self.ports_10g_spin.setRange(0, 128)
        ports_form.addRow("10G (SFP+/RJ45, iSCSI/NAS)", self.ports_10g_spin)

        self.ports_25g_spin = QSpinBox()
        self.ports_25g_spin.setRange(0, 128)
        ports_form.addRow("25G (SFP28)", self.ports_25g_spin)

        self.ports_40g_spin = QSpinBox()
        self.ports_40g_spin.setRange(0, 128)
        ports_form.addRow("40G (QSFP+)", self.ports_40g_spin)

        self.ports_100g_spin = QSpinBox()
        self.ports_100g_spin.setRange(0, 128)
        ports_form.addRow("100G (QSFP28)", self.ports_100g_spin)

        self.ports_fc_spin = QSpinBox()
        self.ports_fc_spin.setRange(0, 128)
        self.ports_fc_spin.setValue(4)
        ports_form.addRow("FC", self.ports_fc_spin)

        self.ports_sas_spin = QSpinBox()
        self.ports_sas_spin.setRange(0, 128)
        self.ports_sas_spin.setToolTip(
            "SAS target ports - for direct-attach links straight to a "
            "server's SAS HBA, no switch in between."
        )
        ports_form.addRow("SAS (direct-attach)", self.ports_sas_spin)

        outer.addWidget(ports_box)

        #
        # Rack sizing - same pattern as Server/NetworkSwitch.
        #

        rack_box = QGroupBox("Rack Sizing (optional)")
        rack_form = QFormLayout(rack_box)

        self.rack_units_spin = QSpinBox()
        self.rack_units_spin.setRange(0, 60)
        self.rack_units_spin.setSuffix(" U")
        self.rack_units_spin.setSpecialValueText("(not set)")
        rack_form.addRow("Rack Size (head unit)", self.rack_units_spin)

        self.power_watts_spin = QDoubleSpinBox()
        self.power_watts_spin.setRange(0.0, 20000.0)
        self.power_watts_spin.setSuffix(" W")
        self.power_watts_spin.setSpecialValueText("(not set)")
        self.power_watts_spin.setToolTip(
            "Use the nameplate/max draw from the datasheet, not \"typical\" - "
            "safer for circuit/PDU capacity planning. Head unit only - "
            "shelves have their own power below."
        )
        rack_form.addRow("Power (head unit)", self.power_watts_spin)

        outer.addWidget(rack_box)

        #
        # Expansion shelves - embedded in this Storage, not a separate
        # top-level entity (a shelf never exists independently of the
        # storage it expands, usually SAS-cabled to the head unit or the
        # previous shelf in a chain).
        #

        shelves_box = QGroupBox("Expansion Shelves (optional)")
        shelves_layout = QVBoxLayout(shelves_box)

        self.shelves_table = QTableWidget(0, 3)
        self.shelves_table.setHorizontalHeaderLabels(["Name", "Size (U)", "Power (W)"])
        self.shelves_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.shelves_table.setMaximumHeight(140)
        shelves_layout.addWidget(self.shelves_table)

        shelves_button_row = QHBoxLayout()
        add_shelf_button = QPushButton("+ Add Shelf")
        add_shelf_button.clicked.connect(self._add_shelf_row)
        shelves_button_row.addWidget(add_shelf_button)

        remove_shelf_button = QPushButton("- Remove Selected")
        remove_shelf_button.clicked.connect(self._remove_selected_shelf_row)
        shelves_button_row.addWidget(remove_shelf_button)
        shelves_button_row.addStretch()

        shelves_layout.addLayout(shelves_button_row)
        outer.addWidget(shelves_box)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(60)
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._uid = None

        if storage is not None:
            self.load(storage)
        else:
            self._recalc_overhead()

    def _recalc_overhead(self) -> None:
        raw = self.raw_spin.value()
        usable = self.usable_spin.value()
        overhead = 0.0 if raw <= 0 else max(0.0, (1 - usable / raw) * 100)
        self.overhead_spin.blockSignals(True)
        self.overhead_spin.setValue(overhead)
        self.overhead_spin.blockSignals(False)

    def _add_shelf_row(self, name: str = "", rack_units: int = 0, power_watts: float = 0.0) -> None:
        row = self.shelves_table.rowCount()
        self.shelves_table.insertRow(row)
        self.shelves_table.setItem(row, 0, QTableWidgetItem(name))
        self.shelves_table.setItem(row, 1, QTableWidgetItem(str(rack_units)))
        self.shelves_table.setItem(row, 2, QTableWidgetItem(str(power_watts)))

    def _remove_selected_shelf_row(self) -> None:
        rows = sorted({idx.row() for idx in self.shelves_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.shelves_table.removeRow(row)

    def load(self, storage: Storage) -> None:
        self._uid = storage.uid
        self.name_edit.setText(storage.name)
        self.site_combo.setCurrentText(storage.site)
        self.vendor_edit.setText(storage.vendor)
        self.model_edit.setText(storage.model)
        self.raw_spin.setValue(storage.raw_capacity_tb)
        self.usable_spin.setValue(storage.usable_capacity_tb)
        self._recalc_overhead()

        self.ports_1g_spin.setValue(storage.ports_1g)
        self.ports_10g_spin.setValue(storage.ports_10g)
        self.ports_25g_spin.setValue(storage.ports_25g)
        self.ports_40g_spin.setValue(storage.ports_40g)
        self.ports_100g_spin.setValue(storage.ports_100g)
        self.ports_fc_spin.setValue(storage.ports_fc)
        self.ports_sas_spin.setValue(storage.ports_sas)

        self.rack_units_spin.setValue(storage.rack_units)
        self.power_watts_spin.setValue(storage.power_watts)

        for shelf in storage.expansion_shelves:
            self._add_shelf_row(shelf.name, shelf.rack_units, shelf.power_watts)

        self.notes_edit.setPlainText(storage.notes)

    def get_storage(self) -> Storage:
        storage = Storage.create_default()

        if self._uid:
            storage.uid = self._uid

        storage.name = self.name_edit.text()
        storage.site = self.site_combo.currentText()
        storage.vendor = self.vendor_edit.text()
        storage.model = self.model_edit.text()
        storage.raw_capacity_tb = self.raw_spin.value()
        storage.usable_capacity_tb = self.usable_spin.value()
        storage.raid_overhead_percent = self.overhead_spin.value()

        storage.ports_1g = self.ports_1g_spin.value()
        storage.ports_10g = self.ports_10g_spin.value()
        storage.ports_25g = self.ports_25g_spin.value()
        storage.ports_40g = self.ports_40g_spin.value()
        storage.ports_100g = self.ports_100g_spin.value()
        storage.ports_fc = self.ports_fc_spin.value()
        storage.ports_sas = self.ports_sas_spin.value()

        storage.rack_units = self.rack_units_spin.value()
        storage.power_watts = self.power_watts_spin.value()

        shelves = []
        for row in range(self.shelves_table.rowCount()):
            name_item = self.shelves_table.item(row, 0)
            u_item = self.shelves_table.item(row, 1)
            w_item = self.shelves_table.item(row, 2)
            try:
                rack_units = int(float(u_item.text())) if u_item and u_item.text() else 0
            except ValueError:
                rack_units = 0
            try:
                power_watts = float(w_item.text()) if w_item and w_item.text() else 0.0
            except ValueError:
                power_watts = 0.0
            shelves.append(StorageShelf(
                name=name_item.text() if name_item else "",
                rack_units=rack_units,
                power_watts=power_watts,
            ))
        storage.expansion_shelves = shelves
        storage.notes = self.notes_edit.toPlainText()

        return storage
