import copy
import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.services.project_service import ProjectService
from src.persistence.csv_io import CsvSchemaError
from src.persistence import csv_io
from src.gui.import_conflict import confirm_import_conflict, ImportConflictChoice

from src.gui.dialogs.storage_dialog import StorageDialog
from src.gui.models.storage_table_model import StorageTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class StoragePage(QWidget):

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = StorageTableModel(
            connections_provider=lambda: self.service.project.connections,
            vms_provider=lambda: self.service.project.vms,
            thresholds_provider=lambda: self.service.thresholds,
            on_change=self.service.touch_storages,
        )

        self._create_ui()

        self.service.storages_changed.connect(self.refresh)
        self.service.network_changed.connect(self.refresh)
        self.service.vms_changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):

        main_layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_storage)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_storage)
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
        self.table.edit_requested.connect(self._edit_storage)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)

        main_layout.addWidget(self.table)

        summary_layout = QHBoxLayout()

        self.card_primary = SummaryWidget("Primary Usable", "0 TB")
        self.card_dr = SummaryWidget("DR Usable", "0 TB")

        summary_layout.addWidget(self.card_primary)
        summary_layout.addWidget(self.card_dr)

        main_layout.addLayout(summary_layout)

    def _selected_storages(self) -> list:
        return [self.model.storage_at(row) for row in self.table.selected_rows()]

    def _add_storage(self):
        dialog = StorageDialog(servers=self.service.project.servers, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.add_storage(dialog.get_storage())

    def _edit_storage(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one storage system in the table.")
            return

        row = rows[0]
        storage = self.model.storage_at(row)
        dialog = StorageDialog(storage, servers=self.service.project.servers, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.update_storage(row, dialog.get_storage())

    def _delete_selected(self):
        storages = self._selected_storages()
        if not storages:
            QMessageBox.information(self, "Delete", "Select at least one storage system in the table.")
            return

        confirm = QMessageBox.question(self, "Delete", f"Delete {len(storages)} storage system(s)?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_storages(storages)

    def _duplicate_selected(self):
        storages = self._selected_storages()
        if not storages:
            QMessageBox.information(self, "Copy", "Select at least one storage system in the table.")
            return

        copies = []
        for storage in storages:
            new_storage = copy.deepcopy(storage)
            new_storage.uid = str(uuid.uuid4())
            new_storage.name = f"{new_storage.name} (copy)" if new_storage.name else new_storage.name
            copies.append(new_storage)

        self.service.add_storages(copies)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Storage CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            new_storages = csv_io.import_storages(path)
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
            return
        choice = confirm_import_conflict(
            self, "storage system", len(self.service.project.storages), len(new_storages),
        )
        if choice == ImportConflictChoice.CANCEL:
            return
        try:
            count = self.service.import_storages_csv(path, replace=choice == ImportConflictChoice.REPLACE)
            QMessageBox.information(self, "Import", f"Imported {count} storage system(s).")
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Storage CSV", "storage.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_storages_csv(path)
            QMessageBox.information(self, "Export", "Storage exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_all(self):
        if not self.service.project.storages:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.storages)} storage system(s)? "
            "You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_storages()

    def refresh(self):
        self.model.set_storages(self.service.project.storages)
        self.table.auto_size_columns()

        project = self.service.project
        self.card_primary.set_value(f"{project.usable_storage_gb('Primary') / 1024:.1f} TB")
        self.card_dr.set_value(f"{project.usable_storage_gb('DR') / 1024:.1f} TB")
