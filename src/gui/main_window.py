from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from ..services.project_service import ProjectService
from ..persistence.project_repository import FILE_EXTENSION
from ..persistence.csv_io import CsvSchemaError

from .pages.dashboard_page import DashboardPage
from .pages.servers_page import ServersPage
from .pages.storage_page import StoragePage
from .pages.virtual_machines_page import VirtualMachinesPage
from .pages.network_page import NetworkPage
from .pages.summary_page import SummaryPage
from .pages.reports_page import ReportsPage
from .pages.settings_page import SettingsPage


class MainWindow(QMainWindow):

    VERSION = "2.0.4"

    def __init__(self, project_service: ProjectService):
        super().__init__()

        self.project_service = project_service

        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        self._create_menu()
        self._create_tabs()
        self._create_statusbar()

        self.project_service.changed.connect(self._update_title)
        self._update_title()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _create_menu(self):

        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        tools_menu = menu.addMenu("&Tools")
        help_menu = menu.addMenu("&Help")

        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        import_action = QAction("Import CSV...", self)
        import_action.triggered.connect(self._import_csv)
        file_menu.addAction(import_action)

        export_action = QAction("Export CSV...", self)
        export_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        rename_action = QAction("Rename Project...", self)
        rename_action.triggered.connect(self._rename_project)
        tools_menu.addAction(rename_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _create_tabs(self):

        tabs = QTabWidget()

        tabs.setDocumentMode(True)
        tabs.setMovable(False)

        tabs.addTab(DashboardPage(self.project_service), "Dashboard")
        tabs.addTab(ServersPage(self.project_service), "Servers")
        tabs.addTab(StoragePage(self.project_service), "Storage")
        tabs.addTab(VirtualMachinesPage(self.project_service), "VMs")
        tabs.addTab(NetworkPage(self.project_service), "Network")
        tabs.addTab(SummaryPage(self.project_service), "Summary")
        tabs.addTab(ReportsPage(self.project_service), "Reports")
        tabs.addTab(SettingsPage(self.project_service), "Settings")

        self.setCentralWidget(tabs)

    def _create_statusbar(self):

        status = QStatusBar()

        status.showMessage("Ready")

        status.addPermanentWidget(
            QLabel(f"v{self.VERSION}")
        )

        self.setStatusBar(status)

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------

    def _update_title(self):
        name = self.project_service.project.name or "New Project"
        dirty_mark = " *" if self.project_service.dirty else ""
        path = self.project_service.current_path
        path_part = f" - {path}" if path else ""
        self.setWindowTitle(f"ClusterSizer {self.VERSION} - {name}{dirty_mark}{path_part}")

    def _confirm_discard_if_dirty(self) -> bool:
        if not self.project_service.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "The current project has unsaved changes. Continue without saving?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _new_project(self):
        if not self._confirm_discard_if_dirty():
            return
        self.project_service.new_project()

    def _open_project(self):
        if not self._confirm_discard_if_dirty():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", f"ClusterSizer Project (*{FILE_EXTENSION})"
        )
        if not path:
            return

        try:
            self.project_service.load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))

    def _save_project(self):
        if self.project_service.current_path is None:
            self._save_project_as()
            return

        try:
            self.project_service.save_project()
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            f"{self.project_service.project.name or 'project'}{FILE_EXTENSION}",
            f"ClusterSizer Project (*{FILE_EXTENSION})",
        )
        if not path:
            return

        if not path.endswith(FILE_EXTENSION):
            path += FILE_EXTENSION

        try:
            self.project_service.save_project(path)
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self, "Rename Project", "Project name:", text=self.project_service.project.name
        )
        if ok and name:
            self.project_service.project.name = name
            self.project_service.touch()

    def _import_csv(self):
        kinds = ["Servers", "Storage", "VMs", "Switches", "Connections"]
        kind, ok = QInputDialog.getItem(self, "Import CSV", "Import into:", kinds, editable=False)
        if not ok:
            return

        path, _ = QFileDialog.getOpenFileName(self, f"Import {kind} CSV", "", "CSV (*.csv)")
        if not path:
            return

        try:
            if kind == "Servers":
                count = self.project_service.import_servers_csv(path)
            elif kind == "Storage":
                count = self.project_service.import_storages_csv(path)
            elif kind == "VMs":
                count = self.project_service.import_vms_csv(path)
            elif kind == "Switches":
                count = self.project_service.import_switches_csv(path)
            else:
                count, _skipped = self.project_service.import_connections_csv(path)
            QMessageBox.information(self, "Import", f"Imported {count} row(s) into {kind}.")
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))

    def _export_csv(self):
        kinds = ["Servers", "Storage", "VMs", "Switches", "Connections"]
        kind, ok = QInputDialog.getItem(self, "Export CSV", "Export:", kinds, editable=False)
        if not ok:
            return

        default_name = {
            "Servers": "servers.csv", "Storage": "storage.csv", "VMs": "vms.csv",
            "Switches": "switches.csv", "Connections": "connections.csv",
        }[kind]
        path, _ = QFileDialog.getSaveFileName(self, f"Export {kind} CSV", default_name, "CSV (*.csv)")
        if not path:
            return

        try:
            if kind == "Servers":
                self.project_service.export_servers_csv(path)
            elif kind == "Storage":
                self.project_service.export_storages_csv(path)
            elif kind == "VMs":
                self.project_service.export_vms_csv(path)
            elif kind == "Switches":
                self.project_service.export_switches_csv(path)
            else:
                self.project_service.export_connections_csv(path)
            QMessageBox.information(self, "Export", f"{kind} exported.")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _show_about(self):
        QMessageBox.information(
            self,
            "About ClusterSizer",
            f"ClusterSizer {self.VERSION}\n\n"
            "Capacity planning tool for virtualized infrastructure: "
            "servers, storage, VMs, and DR sizing.",
        )

    def closeEvent(self, event):
        if self._confirm_discard_if_dirty():
            event.accept()
        else:
            event.ignore()
