import copy
import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.services.project_service import ProjectService
from src.persistence.csv_io import CsvSchemaError
from src.persistence import csv_io
from src.gui.import_conflict import confirm_import_conflict, ImportConflictChoice
from src.calculations.backup import compute_compliance

from src.gui.dialogs.backup_destination_dialog import BackupDestinationDialog
from src.gui.models.backup_table_model import BackupDestinationTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class BackupPage(QWidget):
    """Backup Destinations - a list, not a single flat config, since a
    real setup usually has several (a fast local repo for restores, plus
    an offsite copy, maybe an immutable/offline one too) and the 3-2-1-1
    compliance check needs something real to count across. Evaluated
    project-wide (not per-site) - see src/calculations/backup.py's
    docstring for why."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = BackupDestinationTableModel(
            on_change=self.service.touch_backup_destinations,
        )

        self._create_ui()

        self.service.backup_changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        intro = QLabel(
            "Backup destinations - where copies of your data actually live. "
            "Add each one you have (local repo, offsite, immutable, etc.) "
            "to see your 3-2-1-1 compliance below."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #757575;")
        main_layout.addWidget(intro)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_destination)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_destination)
        toolbar.addAction(edit_action)

        delete_action = QAction("🗑 Delete", self)
        delete_action.triggered.connect(self._delete_selected)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        duplicate_action = QAction("📄 Duplicate", self)
        duplicate_action.triggered.connect(self._duplicate_selected)
        toolbar.addAction(duplicate_action)

        toolbar.addSeparator()

        import_action = QAction("📥 Import CSV", self)
        import_action.triggered.connect(self._import_csv)
        toolbar.addAction(import_action)

        export_action = QAction("📤 Export CSV", self)
        export_action.triggered.connect(self._export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        clear_action = QAction("🧹 Clear All", self)
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        main_layout.addWidget(toolbar)

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_destination)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)

        main_layout.addWidget(self.table)

        summary_layout = QHBoxLayout()

        self.card_count = SummaryWidget("Destinations", "0")
        self.card_effective = SummaryWidget("Total Effective", "0 TB")
        self.card_compliance = SummaryWidget("3-2-1-1", "-")

        summary_layout.addWidget(self.card_count)
        summary_layout.addWidget(self.card_effective)
        summary_layout.addWidget(self.card_compliance)

        main_layout.addLayout(summary_layout)

        self.compliance_detail_label = QLabel("")
        self.compliance_detail_label.setWordWrap(True)
        self.compliance_detail_label.setStyleSheet("color: #ed6c02; font-style: italic;")
        main_layout.addWidget(self.compliance_detail_label)

    def _selected_destinations(self) -> list:
        return [self.model.destination_at(row) for row in self.table.selected_rows()]

    def _add_destination(self):
        dialog = BackupDestinationDialog(sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.add_backup_destination(dialog.get_destination())

    def _edit_destination(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one backup destination in the table.")
            return

        row = rows[0]
        destination = self.model.destination_at(row)
        dialog = BackupDestinationDialog(destination, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.update_backup_destination(row, dialog.get_destination())

    def _delete_selected(self):
        destinations = self._selected_destinations()
        if not destinations:
            QMessageBox.information(self, "Delete", "Select at least one backup destination in the table.")
            return

        confirm = QMessageBox.question(self, "Delete", f"Delete {len(destinations)} backup destination(s)?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_backup_destinations(destinations)

    def _duplicate_selected(self):
        destinations = self._selected_destinations()
        if not destinations:
            QMessageBox.information(self, "Copy", "Select at least one backup destination in the table.")
            return

        copies = []
        for d in destinations:
            new_d = copy.deepcopy(d)
            new_d.uid = str(uuid.uuid4())
            new_d.name = f"{new_d.name} (copy)" if new_d.name else new_d.name
            copies.append(new_d)

        self.service.add_backup_destinations(copies)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Backup Destinations CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            new_destinations = csv_io.import_backup_destinations(path)
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
            return
        choice = confirm_import_conflict(
            self, "backup destination", len(self.service.project.backup_destinations), len(new_destinations),
        )
        if choice == ImportConflictChoice.CANCEL:
            return
        try:
            count = self.service.import_backup_destinations_csv(path, replace=choice == ImportConflictChoice.REPLACE)
            QMessageBox.information(self, "Import", f"Imported {count} backup destination(s).")
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Backup Destinations CSV", "backup_destinations.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_backup_destinations_csv(path)
            QMessageBox.information(self, "Export", "Backup destinations exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_all(self):
        if not self.service.project.backup_destinations:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.backup_destinations)} backup destination(s)? "
            "You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_backup_destinations()

    def refresh(self):
        destinations = self.service.project.backup_destinations
        self.model.set_destinations(destinations)
        self.table.auto_size_columns()

        self.card_count.set_value(str(len(destinations)))
        total_effective = sum(d.effective_capacity_tb for d in destinations)
        self.card_effective.set_value(f"{total_effective:.1f} TB")

        check = compute_compliance(destinations)
        if check.meets_3_2_1_1:
            self.card_compliance.set_value("\u2705 Full")
            self.compliance_detail_label.setText("")
        elif check.meets_3_2_1:
            self.card_compliance.set_value("\u26a0 3-2-1 only")
            self.compliance_detail_label.setText(
                "Meets classic 3-2-1, but not the modern 3-2-1-1: " + "; ".join(check.missing) + "."
            )
        else:
            self.card_compliance.set_value("\u274c Not met")
            self.compliance_detail_label.setText(
                "Missing: " + "; ".join(check.missing) + "."
            )
