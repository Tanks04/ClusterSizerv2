from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
)

from src.models.storage import Storage


class StorageDialog(QDialog):

    def __init__(self, storage: Storage | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Storage")

        self.resize(420, 340)

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
            "Izračunato automatski iz Raw/Usable (RAID, erasure coding, itd.)"
        )
        layout.addRow("RAID/EC Overhead", self.overhead_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

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

    def load(self, storage: Storage) -> None:
        self._uid = storage.uid
        self.name_edit.setText(storage.name)
        self.site_combo.setCurrentText(storage.site)
        self.vendor_edit.setText(storage.vendor)
        self.model_edit.setText(storage.model)
        self.raw_spin.setValue(storage.raw_capacity_tb)
        self.usable_spin.setValue(storage.usable_capacity_tb)
        self._recalc_overhead()

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

        return storage
