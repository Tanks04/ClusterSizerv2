from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QDoubleSpinBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.storage import Storage, StorageShelf
from src.calculations.hci_storage import compute_hci_raw_capacity


class StorageDialog(QDialog):

    def __init__(self, storage: Storage | None = None, servers: list | None = None, sites: list | None = None, parent=None):
        super().__init__(parent)

        self._servers = servers or []

        self.setWindowTitle("Storage")

        self.resize(440, 620)

        # See ServerDialog for why this is scrollable - the form has
        # grown taller than a lot of screens can show at once, with no
        # other way to reach the bottom.
        dialog_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        outer = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        dialog_layout.addWidget(scroll_area)

        layout = QFormLayout()
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(sites or ["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vendor_edit = QLineEdit()
        layout.addRow("Vendor", self.vendor_edit)

        self.model_edit = QLineEdit()
        layout.addRow("Model", self.model_edit)

        self.is_hci_check = QCheckBox("HCI (vSAN, Storage Spaces Direct, Nutanix AHV, etc.)")
        self.is_hci_check.setToolTip(
            "No separate physical array - the disks live in the servers, "
            "but the cluster still behaves like one shared storage pool. "
            "Check which servers contribute below; Raw Capacity is then "
            "auto-summed from their Local Disk (Raw) field instead of "
            "typed in directly."
        )
        self.is_hci_check.toggled.connect(self._on_hci_toggled)
        layout.addRow("", self.is_hci_check)

        self.hci_servers_box = QGroupBox("Linked Servers (contribute local disk to Raw Capacity)")
        hci_servers_layout = QVBoxLayout(self.hci_servers_box)
        self.hci_servers_list = QListWidget()
        self.hci_servers_list.setMinimumHeight(160)
        self.hci_servers_list.setMaximumHeight(220)
        self.hci_servers_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.hci_servers_list.itemChanged.connect(self._recalc_hci_raw_capacity)
        hci_servers_layout.addWidget(self.hci_servers_list)
        self.hci_servers_box.setVisible(False)
        outer.addWidget(self.hci_servers_box)

        self.raw_spin = QDoubleSpinBox()
        self.raw_spin.setDecimals(2)
        self.raw_spin.setRange(0.0, 100000.0)
        self.raw_spin.setSingleStep(1.0)
        self.raw_spin.setSuffix(" TB")
        self.raw_spin.setValue(100.0)
        self.raw_spin.valueChanged.connect(self._recalc_overhead)
        layout.addRow("Raw Capacity", self.raw_spin)

        self.usable_spin = QDoubleSpinBox()
        self.usable_spin.setDecimals(2)
        self.usable_spin.setRange(0.0, 100000.0)
        self.usable_spin.setSingleStep(1.0)
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
        # Pricing - head unit only, each shelf has its own in the table below.
        #

        pricing_box = QGroupBox("Pricing (optional, head unit)")
        pricing_form = QFormLayout(pricing_box)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 10_000_000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setSuffix(" EUR")
        self.price_spin.setSpecialValueText("(not set)")
        pricing_form.addRow("Price", self.price_spin)

        outer.addWidget(pricing_box)

        #
        # Expansion shelves - embedded in this Storage, not a separate
        # top-level entity (a shelf never exists independently of the
        # storage it expands, usually SAS-cabled to the head unit or the
        # previous shelf in a chain).
        #

        shelves_box = QGroupBox("Expansion Shelves (optional)")
        shelves_layout = QVBoxLayout(shelves_box)

        self.shelves_table = QTableWidget(0, 4)
        self.shelves_table.setHorizontalHeaderLabels(["Name", "Size (U)", "Power (W)", "Price (EUR)"])
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
        dialog_layout.addWidget(buttons)

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

    _UNTOUCHED_USABLE_DEFAULT = 80.0  # matches the QDoubleSpinBox's own construction-time default below

    def _on_hci_toggled(self, checked: bool) -> None:
        self.hci_servers_box.setVisible(checked)
        # setReadOnly() alone does NOT block the spinner's up/down
        # buttons or mouse-wheel stepping in Qt - only direct keyboard
        # typing. A user could still nudge Raw Capacity via the arrows
        # even though it's meant to be fully auto-computed while HCI is
        # checked. setEnabled() properly blocks all of that.
        self.raw_spin.setEnabled(not checked)
        self.raw_spin.setToolTip(
            "Auto-summed from the checked servers' Local Disk (Raw) - "
            "uncheck HCI above to type a value directly." if checked else ""
        )
        if checked:
            if self.hci_servers_list.count() == 0:
                # First time this dialog has shown the list (a new/"Add"
                # Storage dialog never calls _populate_hci_server_list()
                # otherwise - only load() does, for editing an existing
                # HCI storage). Guarded on count() so re-toggling HCI off
                # and back on within one session doesn't wipe out
                # whatever was already checked.
                self._populate_hci_server_list()
            self._recalc_hci_raw_capacity()
            # The 80.0 default (a leftover from the pre-HCI days, sized
            # for a traditional array) becomes actively misleading once
            # Raw Capacity auto-sums to something much smaller from real
            # servers - "80TB usable" sitting next to "0TB" or "32TB raw"
            # looks like a real number but describes a physically
            # impossible array. Only reset it if it's still the
            # untouched default - never clobber a value the user already
            # typed themselves, in this session or a previously saved one
            # (load() sets the real saved value AFTER this fires, so an
            # existing HCI storage being edited ends up correct either way).
            if self.usable_spin.value() == self._UNTOUCHED_USABLE_DEFAULT:
                self.usable_spin.setValue(0.0)

    def _populate_hci_server_list(self, checked_uids: set[str] | None = None) -> None:
        checked_uids = checked_uids or set()
        self.hci_servers_list.blockSignals(True)
        self.hci_servers_list.clear()
        for server in self._servers:
            label = f"{server.name} ({server.site}) - {server.local_disk_raw_tb:g} TB local disk"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if server.uid in checked_uids else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, server.uid)
            self.hci_servers_list.addItem(item)
        self.hci_servers_list.blockSignals(False)

    def _recalc_hci_raw_capacity(self) -> None:
        checked_uids = [
            self.hci_servers_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.hci_servers_list.count())
            if self.hci_servers_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        total = compute_hci_raw_capacity(self._servers, checked_uids)
        self.raw_spin.blockSignals(True)
        self.raw_spin.setValue(total)
        self.raw_spin.blockSignals(False)
        self._recalc_overhead()

    def _add_shelf_row(
        self, name: str = "", rack_units: int = 0, power_watts: float = 0.0, price: float = 0.0,
    ) -> None:
        row = self.shelves_table.rowCount()
        self.shelves_table.insertRow(row)
        self.shelves_table.setItem(row, 0, QTableWidgetItem(name))
        self.shelves_table.setItem(row, 1, QTableWidgetItem(str(rack_units)))
        self.shelves_table.setItem(row, 2, QTableWidgetItem(str(power_watts)))
        self.shelves_table.setItem(row, 3, QTableWidgetItem(str(price)))

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

        self._populate_hci_server_list(set(storage.hci_server_uids))
        self.is_hci_check.setChecked(storage.is_hci)
        self.hci_servers_box.setVisible(storage.is_hci)
        self.raw_spin.setReadOnly(storage.is_hci)
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
        self.price_spin.setValue(storage.price)

        for shelf in storage.expansion_shelves:
            self._add_shelf_row(shelf.name, shelf.rack_units, shelf.power_watts, shelf.price)

        self.notes_edit.setPlainText(storage.notes)

    def get_storage(self) -> Storage:
        storage = Storage.create_default()

        if self._uid:
            storage.uid = self._uid

        storage.name = self.name_edit.text()
        storage.site = self.site_combo.currentText()
        storage.vendor = self.vendor_edit.text()
        storage.model = self.model_edit.text()

        storage.is_hci = self.is_hci_check.isChecked()
        checked_uids = [
            self.hci_servers_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.hci_servers_list.count())
            if self.hci_servers_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        storage.hci_server_uids = checked_uids
        storage.raw_capacity_tb = (
            compute_hci_raw_capacity(self._servers, checked_uids)
            if storage.is_hci else self.raw_spin.value()
        )
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
        storage.price = self.price_spin.value()

        shelves = []
        for row in range(self.shelves_table.rowCount()):
            name_item = self.shelves_table.item(row, 0)
            u_item = self.shelves_table.item(row, 1)
            w_item = self.shelves_table.item(row, 2)
            price_item = self.shelves_table.item(row, 3)
            try:
                rack_units = int(float(u_item.text())) if u_item and u_item.text() else 0
            except ValueError:
                rack_units = 0
            try:
                power_watts = float(w_item.text()) if w_item and w_item.text() else 0.0
            except ValueError:
                power_watts = 0.0
            try:
                shelf_price = float(price_item.text()) if price_item and price_item.text() else 0.0
            except ValueError:
                shelf_price = 0.0
            shelves.append(StorageShelf(
                name=name_item.text() if name_item else "",
                rack_units=rack_units,
                power_watts=power_watts,
                price=shelf_price,
            ))
        storage.expansion_shelves = shelves
        storage.notes = self.notes_edit.toPlainText()

        return storage
