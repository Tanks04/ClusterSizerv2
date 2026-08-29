import copy
import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
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

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.models.server_table_model import ServerTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.status_badge import WARNING_COLOR
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class ServersPage(QWidget):

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = ServerTableModel(on_change=self.service.touch_servers)

        self._create_ui()

        self.service.servers_changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):

        main_layout = QVBoxLayout(self)

        #
        # Toolbar
        #

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_server)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_server)
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

        toolbar.addSeparator()

        self.ht_global_check = QCheckBox("Hyperthreading (all servers)")
        self.ht_global_check.setToolTip(
            "Checked when EVERY server currently has HT on. Click to set "
            "HT on or off for ALL servers at once - one bulk change, "
            "undoable with Ctrl+Z like any other action."
        )
        self.ht_global_check.clicked.connect(self._on_ht_global_clicked)
        toolbar.addWidget(self.ht_global_check)

        self.ht_status_label = QLabel("")
        toolbar.addWidget(self.ht_status_label)

        main_layout.addWidget(toolbar)

        #
        # Table
        #

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_server)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)
        self.table.set_custom_actions([
            ("\U0001f6d1 Disable (exclude from capacity)", lambda: self._set_enabled_for_selected(False)),
            ("\u2705 Enable", lambda: self._set_enabled_for_selected(True)),
        ])

        main_layout.addWidget(self.table)

        #
        # Summary
        #

        summary_layout = QHBoxLayout()

        self.card_servers = SummaryWidget("Servers", "0")
        self.card_cores = SummaryWidget("Total Cores", "0")
        self.card_threads = SummaryWidget("Effective Cores (HT)", "0")
        self.card_ram = SummaryWidget("Total RAM", "0 GB")

        for card in (self.card_servers, self.card_cores, self.card_threads, self.card_ram):
            summary_layout.addWidget(card)

        main_layout.addLayout(summary_layout)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_servers(self) -> list:
        return [self.model.server_at(row) for row in self.table.selected_rows()]

    def _set_enabled_for_selected(self, enabled: bool):
        servers = self._selected_servers()
        if not servers:
            return
        self.service.set_enabled_for_servers(servers, enabled)

    def _add_server(self):
        dialog = ServerDialog(sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.add_servers(dialog.get_servers())

    def _edit_server(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one server in the table.")
            return

        row = rows[0]
        server = self.model.server_at(row)
        dialog = ServerDialog(server, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.update_server(row, dialog.get_server())

    def _delete_selected(self):
        servers = self._selected_servers()
        if not servers:
            QMessageBox.information(self, "Delete", "Select at least one server in the table.")
            return

        names = ", ".join(s.name or s.model or "?" for s in servers[:5])
        suffix = "..." if len(servers) > 5 else ""
        confirm = QMessageBox.question(
            self, "Delete", f"Delete {len(servers)} server(s)? [{names}{suffix}]"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_servers(servers)

    def _duplicate_selected(self):
        servers = self._selected_servers()
        if not servers:
            QMessageBox.information(self, "Copy", "Select at least one server in the table.")
            return

        copies = []
        for server in servers:
            new_server = copy.deepcopy(server)
            new_server.uid = str(uuid.uuid4())
            new_server.name = f"{new_server.name} (copy)" if new_server.name else new_server.name
            copies.append(new_server)

        self.service.add_servers(copies)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Servers CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.service.import_servers_csv(path)
            QMessageBox.information(self, "Import", f"Imported {count} server(s).")
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Servers CSV", "servers.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_servers_csv(path)
            QMessageBox.information(self, "Export", "Servers exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_all(self):
        if not self.service.project.servers:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.servers)} server(s)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_servers()

    def _on_ht_global_clicked(self, checked: bool):
        self.service.set_all_servers_hyperthreading(checked)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        self.model.set_servers(self.service.project.servers)
        self.table.auto_size_columns()

        project = self.service.project
        self.card_servers.set_value(project.server_count)
        self.card_cores.set_value(project.total_cores)
        self.card_threads.set_value(project.total_effective_cores)
        self.card_ram.set_value(f"{project.total_ram} GB")

        self._refresh_ht_global()

    def _refresh_ht_global(self):
        summary = self.service.project.hyperthreading_summary()

        if summary.state == "no_servers":
            self.ht_global_check.setChecked(False)
            self.ht_global_check.setEnabled(False)
            self.ht_status_label.setText("")
            return

        self.ht_global_check.setEnabled(True)

        if summary.state == "all_on":
            self.ht_global_check.setChecked(True)
            self.ht_status_label.setText("")
        elif summary.state == "all_off":
            self.ht_global_check.setChecked(False)
            self.ht_status_label.setText("")
        else:  # mixed
            self.ht_global_check.setChecked(False)
            self.ht_status_label.setText(
                f"({summary.on_count}/{summary.total_count} have HT on - click to normalize)"
            )
            self.ht_status_label.setStyleSheet(f"color: {WARNING_COLOR}; font-weight: bold;")
            return

        self.ht_status_label.setStyleSheet("")
