from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.services.project_service import ProjectService
from src.persistence.csv_io import CsvSchemaError
from src.calculations.pricing import compute_equipment_pricing, compute_maintenance_status

from src.gui.dialogs.maintenance_item_dialog import MaintenanceItemDialog
from src.gui.models.maintenance_item_table_model import MaintenanceItemTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error

import copy
import uuid


def _eur(amount: float) -> str:
    return f"\u20ac{amount:,.2f}"


class PricingPage(QWidget):
    """Two simple, unrelated things for admins - not a sales quote:

    1. Equipment pricing - Price is entered directly on Servers/Storage/
       Network/Backup (no re-entry here), this page just totals it up
       by category.
    2. Licenses/Warranties/Maintenance - a renewal-reminder list
       (what it is, what it costs, how long it lasts, when it expires),
       flagged if expired or expiring soon.

    Listens to the general `service.changed` signal, not a narrower
    one - the equipment total depends on Server/Storage/Switch/Backup
    data that isn't itself a "pricing" change, avoiding the staleness
    bug found and fixed on the VMs tab earlier in this project."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = MaintenanceItemTableModel(on_change=self.service.touch_pricing)

        self._create_ui()

        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Equipment pricing summary ---
        equipment_box = QGroupBox("Equipment Pricing (from Servers / Storage / Network / Backup)")
        equipment_layout = QGridLayout(equipment_box)

        self.equipment_cards = {}
        for i, category in enumerate(["Servers", "Storage", "Network", "Backup"]):
            card = SummaryWidget(category, "\u20ac0", compact=True)
            self.equipment_cards[category] = card
            equipment_layout.addWidget(card, 0, i)

        self.card_equipment_total = SummaryWidget("Total Equipment Price", "\u20ac0", compact=True)
        equipment_layout.addWidget(self.card_equipment_total, 1, 0, 1, 4)

        main_layout.addWidget(equipment_box)

        # --- Licenses / Warranties / Maintenance ---
        main_layout.addWidget(QLabel("Licenses, Warranties & Maintenance"))

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("\u2795 Add", self)
        add_action.triggered.connect(self._add_item)
        toolbar.addAction(add_action)

        edit_action = QAction("\u270f Edit", self)
        edit_action.triggered.connect(self._edit_item)
        toolbar.addAction(edit_action)

        delete_action = QAction("\U0001f5d1 Delete", self)
        delete_action.triggered.connect(self._delete_selected)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        duplicate_action = QAction("\U0001f4c4 Duplicate", self)
        duplicate_action.triggered.connect(self._duplicate_selected)
        toolbar.addAction(duplicate_action)

        toolbar.addSeparator()

        import_action = QAction("\U0001f4e5 Import CSV", self)
        import_action.triggered.connect(self._import_csv)
        toolbar.addAction(import_action)

        export_action = QAction("\U0001f4e4 Export CSV", self)
        export_action.triggered.connect(self._export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        clear_action = QAction("\U0001f9f9 Clear All", self)
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        main_layout.addWidget(toolbar)

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_item)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)

        main_layout.addWidget(self.table, stretch=1)

        summary_row = QGridLayout()
        self.card_maintenance_count = SummaryWidget("Tracked Items", "0", compact=True)
        self.card_expired = SummaryWidget("Expired", "0", compact=True)
        self.card_expiring_soon = SummaryWidget("Expiring Soon (90d)", "0", compact=True)
        summary_row.addWidget(self.card_maintenance_count, 0, 0)
        summary_row.addWidget(self.card_expired, 0, 1)
        summary_row.addWidget(self.card_expiring_soon, 0, 2)
        main_layout.addLayout(summary_row)

    def _selected_items(self) -> list:
        return [self.model.item_at(row) for row in self.table.selected_rows()]

    def _add_item(self):
        dialog = MaintenanceItemDialog(parent=self)
        if dialog.exec():
            self.service.add_maintenance_item(dialog.get_item())

    def _edit_item(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one item in the table.")
            return

        row = rows[0]
        item = self.model.item_at(row)
        dialog = MaintenanceItemDialog(item, parent=self)
        if dialog.exec():
            self.service.update_maintenance_item(row, dialog.get_item())

    def _delete_selected(self):
        items = self._selected_items()
        if not items:
            QMessageBox.information(self, "Delete", "Select at least one item in the table.")
            return

        confirm = QMessageBox.question(self, "Delete", f"Delete {len(items)} item(s)?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_maintenance_items(items)

    def _duplicate_selected(self):
        items = self._selected_items()
        if not items:
            QMessageBox.information(self, "Copy", "Select at least one item in the table.")
            return

        for i in items:
            new_i = copy.deepcopy(i)
            new_i.uid = str(uuid.uuid4())
            new_i.name = f"{new_i.name} (copy)" if new_i.name else new_i.name
            self.service.add_maintenance_item(new_i)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Maintenance Items CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.service.import_maintenance_items_csv(path)
            QMessageBox.information(self, "Import", f"Imported {count} item(s).")
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Maintenance Items CSV", "maintenance_items.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_maintenance_items_csv(path)
            QMessageBox.information(self, "Export", "Items exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_all(self):
        if not self.service.project.maintenance_items:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.maintenance_items)} item(s)? "
            "You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_maintenance_items()

    def refresh(self):
        project = self.service.project
        self.model.set_items(project.maintenance_items)
        self.table.auto_size_columns()

        summary = compute_equipment_pricing(project)
        for category, card in self.equipment_cards.items():
            card.set_value(_eur(summary.by_category.get(category, 0.0)))
        self.card_equipment_total.set_value(_eur(summary.total))

        statuses = compute_maintenance_status(project)
        expired = sum(1 for s in statuses if s.status == "expired")
        expiring_soon = sum(1 for s in statuses if s.status == "expiring_soon")

        self.card_maintenance_count.set_value(str(len(project.maintenance_items)))
        self.card_expired.set_value(str(expired))
        self.card_expiring_soon.set_value(str(expiring_soon))
