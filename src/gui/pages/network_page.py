import copy
import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from src.services.project_service import ProjectService
from src.persistence.csv_io import CsvSchemaError
from src.calculations.networking import site_port_usage, format_usage, any_over_committed
from src.models.cluster_project import PRIMARY, DR

from src.gui.dialogs.switch_dialog import SwitchDialog
from src.gui.dialogs.connection_dialog import ConnectionDialog
from src.gui.models.switch_table_model import SwitchTableModel
from src.gui.models.connection_table_model import ConnectionTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class NetworkPage(QWidget):
    """Network tab: switches (port inventory) + server<->switch connections.
    Fully optional - if left unfilled, the rest of the tool works normally."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self.switch_model = SwitchTableModel(
            connections_provider=lambda: self.service.project.connections,
        )
        self.connection_model = ConnectionTableModel(
            servers_provider=lambda: self.service.project.servers,
            switches_provider=lambda: self.service.project.switches,
            storages_provider=lambda: self.service.project.storages,
        )

        self._create_ui()

        self.service.network_changed.connect(self.refresh)
        self.service.servers_changed.connect(self.refresh)
        self.service.storages_changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        #
        # Overview
        #

        overview_layout = QHBoxLayout()
        self.card_switches = SummaryWidget("Switches", "0")
        self.card_connections = SummaryWidget("Connections", "0")
        self.card_primary_ports = SummaryWidget("Primary Ports Used/Free", "-")
        self.card_dr_ports = SummaryWidget("DR Ports Used/Free", "-")

        for card in (
            self.card_switches, self.card_connections,
            self.card_primary_ports, self.card_dr_ports,
        ):
            overview_layout.addWidget(card)

        main_layout.addLayout(overview_layout)

        note = QLabel(
            "Network data is optional - if you don't fill it in, the rest of "
            "the tool works normally. Filling it in just helps you see free/used ports."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #757575; font-style: italic;")
        main_layout.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        splitter.addWidget(self._build_switches_section())
        splitter.addWidget(self._build_connections_section())
        splitter.setSizes([300, 300])

    def _build_switches_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("<b>Switches</b>"))

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_switch)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_switch)
        toolbar.addAction(edit_action)

        delete_action = QAction("🗑 Delete", self)
        delete_action.triggered.connect(self._delete_switches)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        duplicate_action = QAction("📄 Duplicate", self)
        duplicate_action.triggered.connect(self._duplicate_switches)
        toolbar.addAction(duplicate_action)

        toolbar.addSeparator()

        import_action = QAction("📥 Import CSV", self)
        import_action.triggered.connect(self._import_switches_csv)
        toolbar.addAction(import_action)

        export_action = QAction("📤 Export CSV", self)
        export_action.triggered.connect(self._export_switches_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        clear_action = QAction("🧹 Clear All", self)
        clear_action.triggered.connect(self._clear_switches)
        toolbar.addAction(clear_action)

        layout.addWidget(toolbar)

        self.switch_table = MultiSelectTableView()
        self.switch_table.set_source_model(self.switch_model)
        self.switch_table.edit_requested.connect(self._edit_switch)
        self.switch_table.delete_requested.connect(self._delete_switches)
        self.switch_table.copy_requested.connect(self._duplicate_switches)

        layout.addWidget(self.switch_table)

        return section

    def _build_connections_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("<b>Connections</b> (Server ↔ Switch)"))

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_connection)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_connection)
        toolbar.addAction(edit_action)

        delete_action = QAction("🗑 Delete", self)
        delete_action.triggered.connect(self._delete_connections)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        duplicate_action = QAction("📄 Duplicate", self)
        duplicate_action.triggered.connect(self._duplicate_connections)
        toolbar.addAction(duplicate_action)

        toolbar.addSeparator()

        import_action = QAction("📥 Import CSV", self)
        import_action.triggered.connect(self._import_connections_csv)
        toolbar.addAction(import_action)

        export_action = QAction("📤 Export CSV", self)
        export_action.triggered.connect(self._export_connections_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        clear_action = QAction("🧹 Clear All", self)
        clear_action.triggered.connect(self._clear_connections)
        toolbar.addAction(clear_action)

        layout.addWidget(toolbar)

        self.connection_table = MultiSelectTableView()
        self.connection_table.set_source_model(self.connection_model)
        self.connection_table.edit_requested.connect(self._edit_connection)
        self.connection_table.delete_requested.connect(self._delete_connections)
        self.connection_table.copy_requested.connect(self._duplicate_connections)

        layout.addWidget(self.connection_table)

        return section

    # ------------------------------------------------------------------
    # Switches - actions
    # ------------------------------------------------------------------

    def _selected_switches(self) -> list:
        return [self.switch_model.switch_at(row) for row in self.switch_table.selected_rows()]

    def _add_switch(self):
        dialog = SwitchDialog(parent=self)
        if dialog.exec():
            self.service.add_switch(dialog.get_switch())

    def _edit_switch(self):
        rows = self.switch_table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one switch in the table.")
            return
        row = rows[0]
        switch = self.switch_model.switch_at(row)
        dialog = SwitchDialog(switch, parent=self)
        if dialog.exec():
            self.service.update_switch(row, dialog.get_switch())

    def _delete_switches(self):
        switches = self._selected_switches()
        if not switches:
            QMessageBox.information(self, "Delete", "Select at least one switch in the table.")
            return
        confirm = QMessageBox.question(
            self, "Delete",
            f"Delete {len(switches)} switch(es)? Connections referencing them "
            "stay as 'orphan' records (they won't be auto-deleted).",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_switches(switches)

    def _duplicate_switches(self):
        switches = self._selected_switches()
        if not switches:
            QMessageBox.information(self, "Copy", "Select at least one switch in the table.")
            return
        copies = []
        for switch in switches:
            new_switch = copy.deepcopy(switch)
            new_switch.uid = str(uuid.uuid4())
            new_switch.name = f"{new_switch.name} (copy)" if new_switch.name else new_switch.name
            copies.append(new_switch)
        self.service.add_switches(copies)

    def _import_switches_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Switches CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.service.import_switches_csv(path)
            QMessageBox.information(self, "Import", f"Imported {count} switch(es).")
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_switches_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Switches CSV", "switches.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_switches_csv(path)
            QMessageBox.information(self, "Export", "Switches exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_switches(self):
        if not self.service.project.switches:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.switches)} switch(es)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_switches()

    # ------------------------------------------------------------------
    # Connections - actions
    # ------------------------------------------------------------------

    def _selected_connections(self) -> list:
        return [self.connection_model.connection_at(row) for row in self.connection_table.selected_rows()]

    def _add_connection(self):
        project = self.service.project
        available_kinds = sum([
            bool(project.servers), bool(project.switches), bool(project.storages),
        ])
        if available_kinds < 2:
            QMessageBox.information(
                self, "Connection",
                "Add at least two of the following before adding a connection: "
                "a server (Servers tab), a switch (above), or a storage system "
                "(Storage tab).",
            )
            return
        dialog = ConnectionDialog(self.service.project, parent=self)
        if dialog.exec():
            self.service.add_connection(dialog.get_connection())

    def _edit_connection(self):
        rows = self.connection_table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one connection in the table.")
            return
        row = rows[0]
        connection = self.connection_model.connection_at(row)
        dialog = ConnectionDialog(
            self.service.project, connection, exclude_uid=connection.uid, parent=self
        )
        if dialog.exec():
            self.service.update_connection(row, dialog.get_connection())

    def _delete_connections(self):
        connections = self._selected_connections()
        if not connections:
            QMessageBox.information(self, "Delete", "Select at least one connection in the table.")
            return
        confirm = QMessageBox.question(self, "Delete", f"Delete {len(connections)} connection(s)?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_connections(connections)

    def _duplicate_connections(self):
        connections = self._selected_connections()
        if not connections:
            QMessageBox.information(self, "Copy", "Select at least one connection in the table.")
            return
        copies = []
        for connection in connections:
            new_conn = copy.deepcopy(connection)
            new_conn.uid = str(uuid.uuid4())
            copies.append(new_conn)
        self.service.add_connections(copies)

    def _import_connections_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Connections CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count, skipped = self.service.import_connections_csv(path)
            msg = f"Imported {count} connection(s)."
            if skipped:
                msg += f" Skipped {skipped} (server/switch name not found in the project)."
            QMessageBox.information(self, "Import", msg)
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _export_connections_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Connections CSV", "connections.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_connections_csv(path)
            QMessageBox.information(self, "Export", "Connections exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_connections(self):
        if not self.service.project.connections:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.connections)} connection(s)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_connections()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        project = self.service.project

        self.switch_model.set_switches(project.switches)
        self.connection_model.set_connections(project.connections)
        self.switch_table.auto_size_columns()
        self.connection_table.auto_size_columns()

        self.card_switches.set_value(len(project.switches))
        self.card_connections.set_value(len(project.connections))

        primary_usage = site_port_usage(project.switches_at(PRIMARY), project.connections)
        dr_usage = site_port_usage(project.switches_at(DR), project.connections)

        primary_text = format_usage(primary_usage)
        dr_text = format_usage(dr_usage)

        self.card_primary_ports.set_value(
            f"⚠ {primary_text}" if any_over_committed(primary_usage) else primary_text
        )
        self.card_dr_ports.set_value(
            f"⚠ {dr_text}" if any_over_committed(dr_usage) else dr_text
        )
