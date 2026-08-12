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

from src.services.project_service import ProjectService
from src.persistence.project_repository import FILE_EXTENSION
from src.version import VERSION as APP_VERSION
from src.persistence.csv_io import CsvSchemaError

from src.gui.pages.servers_page import ServersPage
from src.gui.pages.storage_page import StoragePage
from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.gui.pages.network_page import NetworkPage
from src.gui.pages.summary_page import SummaryPage
from src.gui.pages.compare_page import ComparePage
from src.gui.pages.reports_page import ReportsPage
from src.gui.pages.settings_page import SettingsPage
from src.gui.widgets.lazy_tab_container import LazyTabContainer
from src.gui.error_handling import report_error


class MainWindow(QMainWindow):

    VERSION = APP_VERSION

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
        edit_menu = menu.addMenu("&Edit")
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

        save_scenario_action = QAction("Save Scenario Copy As...", self)
        save_scenario_action.setToolTip(
            "Save a snapshot of the current project to a new file, without "
            "switching your active project to it - branch off a scenario to "
            "compare later on the Compare tab, keep editing the original here."
        )
        save_scenario_action.triggered.connect(self._save_scenario_copy)
        file_menu.addAction(save_scenario_action)

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

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self._undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self._redo)
        edit_menu.addAction(self.redo_action)

        self.project_service.undo_state_changed.connect(self._update_undo_redo_actions)
        self._update_undo_redo_actions()

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

        # Lazy construction: each page is only actually built the first
        # time its tab becomes visible, never "constructed now, shown
        # later" - see LazyTabContainer's docstring for why that matters
        # on Windows.
        page_specs = [
            ("Summary", lambda: SummaryPage(self.project_service)),
            ("Servers", lambda: ServersPage(self.project_service)),
            ("Storage", lambda: StoragePage(self.project_service)),
            ("VMs", lambda: VirtualMachinesPage(self.project_service)),
            ("Network", lambda: NetworkPage(self.project_service)),
            ("Compare", lambda: ComparePage(self.project_service)),
            ("Reports", lambda: ReportsPage(self.project_service)),
            ("Settings", lambda: SettingsPage(self.project_service)),
        ]

        self._tab_containers: list[LazyTabContainer] = []
        for label, factory in page_specs:
            container = LazyTabContainer(factory)
            tabs.addTab(container, label)
            self._tab_containers.append(container)

        tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs = tabs

        self.setCentralWidget(tabs)

        # Build whichever tab is visible right away (index 0, Summary) -
        # that one genuinely is being shown immediately, so it's not part
        # of the hidden-then-shown pattern this is working around.
        self._on_tab_changed(tabs.currentIndex())

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < len(self._tab_containers):
            self._tab_containers[index].ensure_built()

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
            report_error(self, "Open Error", exc)

    def _save_project(self):
        if self.project_service.current_path is None:
            self._save_project_as()
            return

        try:
            self.project_service.save_project()
            self._update_title()
        except Exception as exc:
            report_error(self, "Save Error", exc)

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
            report_error(self, "Save Error", exc)

    def _save_scenario_copy(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario Copy As",
            f"{self.project_service.project.name or 'scenario'}{FILE_EXTENSION}",
            f"ClusterSizer Project (*{FILE_EXTENSION})",
        )
        if not path:
            return

        if not path.endswith(FILE_EXTENSION):
            path += FILE_EXTENSION

        try:
            self.project_service.save_copy_as(path)
            QMessageBox.information(
                self, "Scenario Saved",
                f"Snapshot saved to:\n{path}\n\n"
                "Your active project is unchanged. On the Compare tab, load this "
                "file into either Scenario A or B (or use \"Use Current Project\" "
                "for whichever slot should reflect what you keep editing here) "
                "to compare it against another scenario.",
            )
        except Exception as exc:
            report_error(self, "Save Error", exc)

    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self, "Rename Project", "Project name:", text=self.project_service.project.name
        )
        if ok and name:
            self.project_service.project.name = name
            self.project_service.touch()

    def _undo(self):
        self.project_service.undo()

    def _redo(self):
        self.project_service.redo()

    def _update_undo_redo_actions(self):
        self.undo_action.setEnabled(self.project_service.can_undo)
        self.redo_action.setEnabled(self.project_service.can_redo)

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
            report_error(self, "Import Error", exc)

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
            report_error(self, "Export Error", exc)

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
