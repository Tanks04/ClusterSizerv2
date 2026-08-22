from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from src.models.backup_destination import BackupDestination, DESTINATION_TYPES


class BackupDestinationDialog(QDialog):

    def __init__(self, destination: BackupDestination | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Backup Destination")
        self.resize(420, 420)

        outer = QVBoxLayout(self)
        layout = QFormLayout()
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(DESTINATION_TYPES)
        layout.addRow("Type", self.type_combo)

        self.software_edit = QLineEdit()
        self.software_edit.setPlaceholderText("e.g. Veeam, CommVault, Veritas...")
        layout.addRow("Backup Software", self.software_edit)

        self.raw_spin = QDoubleSpinBox()
        self.raw_spin.setDecimals(2)
        self.raw_spin.setRange(0.0, 100000.0)
        self.raw_spin.setSuffix(" TB")
        self.raw_spin.setValue(20.0)
        layout.addRow("Raw Capacity", self.raw_spin)

        self.dedup_spin = QDoubleSpinBox()
        self.dedup_spin.setDecimals(1)
        self.dedup_spin.setRange(0.1, 100.0)
        self.dedup_spin.setValue(1.0)
        self.dedup_spin.setSuffix(" : 1")
        self.dedup_spin.setToolTip(
            "Deduplication/compression ratio - how much MORE logical data "
            "this destination can hold versus its raw capacity. 1:1 means "
            "no dedup assumed."
        )
        layout.addRow("Dedup Ratio", self.dedup_spin)

        self.offsite_check = QCheckBox("Offsite (geographically separate)")
        self.offsite_check.setToolTip(
            "Protects against a site-level disaster (fire, flood) - part of "
            "the classic 3-2-1 rule's \"1 offsite\" requirement."
        )
        layout.addRow("", self.offsite_check)

        self.immutable_check = QCheckBox("Immutable / Offline")
        self.immutable_check.setToolTip(
            "Physically or logically disconnected, or write-once/immutable - "
            "protects this copy even if ransomware reaches every online "
            "system. The \"+1\" in the modern 3-2-1-1 rule."
        )
        layout.addRow("", self.immutable_check)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(70)
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._uid = None

        if destination is not None:
            self.load(destination)

    def load(self, destination: BackupDestination) -> None:
        self._uid = destination.uid
        self.name_edit.setText(destination.name)
        self.site_combo.setCurrentText(destination.site)
        self.type_combo.setCurrentText(destination.destination_type)
        self.software_edit.setText(destination.backup_software)
        self.raw_spin.setValue(destination.raw_capacity_tb)
        self.dedup_spin.setValue(destination.dedup_ratio)
        self.offsite_check.setChecked(destination.is_offsite)
        self.immutable_check.setChecked(destination.is_immutable)
        self.notes_edit.setPlainText(destination.notes)

    def get_destination(self) -> BackupDestination:
        destination = BackupDestination.create_default()

        if self._uid:
            destination.uid = self._uid

        destination.name = self.name_edit.text()
        destination.site = self.site_combo.currentText()
        destination.destination_type = self.type_combo.currentText()
        destination.backup_software = self.software_edit.text()
        destination.raw_capacity_tb = self.raw_spin.value()
        destination.dedup_ratio = self.dedup_spin.value()
        destination.is_offsite = self.offsite_check.isChecked()
        destination.is_immutable = self.immutable_check.isChecked()
        destination.notes = self.notes_edit.toPlainText()

        return destination
