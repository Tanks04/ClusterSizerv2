from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from src.models.maintenance_item import CATEGORIES, MaintenanceItem


class MaintenanceItemDialog(QDialog):

    def __init__(self, item: MaintenanceItem | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("License / Warranty / Maintenance")
        self.resize(420, 400)

        outer = QVBoxLayout(self)
        layout = QFormLayout()
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Firewall subscription, Server warranty...")
        layout.addRow("Name", self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        layout.addRow("Category", self.category_combo)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0.0, 10_000_000.0)
        self.cost_spin.setDecimals(2)
        self.cost_spin.setSuffix(" EUR")
        self.cost_spin.setToolTip("Total cost for the whole duration below - not a monthly rate.")
        layout.addRow("Cost", self.cost_spin)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 120)
        self.duration_spin.setValue(12)
        self.duration_spin.setSuffix(" months")
        layout.addRow("Duration", self.duration_spin)

        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("e.g. 2026-01-01")
        layout.addRow("Start Date", self.start_date_edit)

        self.expiry_date_edit = QLineEdit()
        self.expiry_date_edit.setPlaceholderText("e.g. 2027-01-01 (YYYY-MM-DD, for the renewal reminder)")
        layout.addRow("Expiry Date", self.expiry_date_edit)

        self.applies_to_edit = QLineEdit()
        self.applies_to_edit.setPlaceholderText("e.g. Firewall FW-01, All ESXi hosts - optional")
        layout.addRow("Applies To", self.applies_to_edit)

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

        if item is not None:
            self.load(item)

    def load(self, item: MaintenanceItem) -> None:
        self._uid = item.uid
        self.name_edit.setText(item.name)
        self.category_combo.setCurrentText(item.category)
        self.cost_spin.setValue(item.cost)
        self.duration_spin.setValue(item.duration_months)
        self.start_date_edit.setText(item.start_date)
        self.expiry_date_edit.setText(item.expiry_date)
        self.applies_to_edit.setText(item.applies_to)
        self.notes_edit.setPlainText(item.notes)

    def get_item(self) -> MaintenanceItem:
        item = MaintenanceItem.create_default()

        if self._uid:
            item.uid = self._uid

        item.name = self.name_edit.text()
        item.category = self.category_combo.currentText()
        item.cost = self.cost_spin.value()
        item.duration_months = self.duration_spin.value()
        item.start_date = self.start_date_edit.text()
        item.expiry_date = self.expiry_date_edit.text()
        item.applies_to = self.applies_to_edit.text()
        item.notes = self.notes_edit.toPlainText()

        return item
