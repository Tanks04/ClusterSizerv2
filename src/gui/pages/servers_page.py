import copy
import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.services.project_service import ProjectService
from src.models.storage import Storage
from src.calculations.hci_storage import compute_hci_raw_capacity
from src.persistence.csv_io import CsvSchemaError
from src.persistence import csv_io
from src.gui.import_conflict import confirm_import_conflict, ImportConflictChoice
from src.gui.dialogs.bulk_edit_dialog import BulkEditDialog, BulkEditField

from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.dialogs.cluster_dialog import ClusterDialog
from src.gui.models.server_table_model import ServerTableModel
from src.gui.models.cluster_table_model import ClusterTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.status_badge import WARNING_COLOR
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class ServersPage(QWidget):

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = ServerTableModel(
            clusters_provider=lambda: self.service.project.clusters,
            on_change=self.service.touch_servers,
        )

        self._create_ui()

        self.service.servers_changed.connect(self.refresh)
        self.service.clusters_changed.connect(self.refresh)
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
            ("\U0001f4be Create HCI Storage from Selected", self._create_hci_storage_from_selected),
            ("\u270f\ufe0f Bulk Edit Selected", self._bulk_edit_selected),
        ])

        main_layout.addWidget(self.table)

        #
        # Clusters - isolated compute failure domains a site can host
        # several of (see src/models/cluster.py for the full picture).
        # Purely optional - assign servers/VMs to one on their own
        # dialogs. Nothing here is required for the app to work as it
        # always has. Placed below the main servers table (not above
        # it) so the servers list stays the first thing visible on
        # this tab, matching every other page's layout.
        #

        cluster_section = QWidget()
        cluster_layout = QVBoxLayout(cluster_section)
        cluster_layout.setContentsMargins(0, 0, 0, 0)

        cluster_layout.addWidget(QLabel(
            "<b>Clusters</b> (isolated failure domains - e.g. separate vSphere/Nutanix/"
            "Proxmox/Hyper-V clusters at the same site - assign servers/VMs to one on "
            "their own dialogs)"
        ))

        cluster_toolbar = QToolBar()
        cluster_toolbar.setMovable(False)

        cluster_add_action = QAction("\u2795 Add", self)
        cluster_add_action.triggered.connect(self._add_cluster)
        cluster_toolbar.addAction(cluster_add_action)

        cluster_edit_action = QAction("\u270f Edit", self)
        cluster_edit_action.triggered.connect(self._edit_cluster)
        cluster_toolbar.addAction(cluster_edit_action)

        cluster_delete_action = QAction("\U0001f5d1 Delete", self)
        cluster_delete_action.triggered.connect(self._delete_clusters)
        cluster_toolbar.addAction(cluster_delete_action)

        cluster_toolbar.addSeparator()

        cluster_clear_action = QAction("\U0001f9f9 Clear All", self)
        cluster_clear_action.triggered.connect(self._clear_clusters)
        cluster_toolbar.addAction(cluster_clear_action)

        cluster_layout.addWidget(cluster_toolbar)

        self.cluster_model = ClusterTableModel(
            servers_provider=lambda: self.service.project.servers,
            vms_provider=lambda: self.service.project.vms,
            thresholds_provider=lambda: self.service.thresholds,
        )
        self.cluster_table = MultiSelectTableView()
        self.cluster_table.set_source_model(self.cluster_model)
        self.cluster_table.edit_requested.connect(self._edit_cluster)
        self.cluster_table.delete_requested.connect(self._delete_clusters)
        cluster_layout.addWidget(self.cluster_table)

        main_layout.addWidget(cluster_section)

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

    def _create_hci_storage_from_selected(self):
        servers = self._selected_servers()
        if not servers:
            QMessageBox.information(self, "Create HCI Storage", "Select at least one server in the table.")
            return

        sites = {s.site for s in servers}
        if len(sites) > 1:
            QMessageBox.warning(
                self, "Create HCI Storage",
                f"Selected servers span multiple sites ({', '.join(sorted(sites))}) - "
                "an HCI cluster's storage lives at one site. Select servers from a "
                "single site only.",
            )
            return

        default_name = f"{servers[0].cluster_name} HCI Storage" if servers[0].cluster_name else "HCI Storage"
        name, ok = QInputDialog.getText(self, "Create HCI Storage", "Storage name:", text=default_name)
        if not ok or not name.strip():
            return

        storage = Storage.create_default()
        storage.name = name.strip()
        storage.site = servers[0].site
        storage.is_hci = True
        storage.hci_server_uids = [s.uid for s in servers]
        storage.raw_capacity_tb = compute_hci_raw_capacity(servers, storage.hci_server_uids)
        storage.usable_capacity_tb = 0.0  # left for the person to set with the FTT calculator

        self.service.add_storage(storage)
        QMessageBox.information(
            self, "Create HCI Storage",
            f"Created '{storage.name}' at {storage.site} linking {len(servers)} server(s) - "
            f"{storage.raw_capacity_tb:.1f} TB raw. Open it on the Storage tab to set Usable "
            "Capacity (the FTT calculator there can estimate it for you).",
        )

    def _bulk_edit_selected(self):
        servers = self._selected_servers()
        if not servers:
            QMessageBox.information(self, "Bulk Edit", "Select at least one server in the table.")
            return

        fields = [
            BulkEditField("sockets", "Sockets", "int", min_value=1, max_value=16),
            BulkEditField("cores_per_socket", "Cores / Socket", "int", min_value=1, max_value=256),
            BulkEditField("hyperthreading_enabled", "Hyperthreading Enabled", "bool"),
            BulkEditField("ram_gb", "RAM", "float", suffix=" GB", max_value=100000, decimals=0),
            BulkEditField("local_disk_count", "Local Disk Count", "int", suffix=" disks"),
            BulkEditField("local_disk_size_tb", "Local Disk Size (each)", "float", suffix=" TB"),
            BulkEditField("nic_10g", "10G NICs", "int", suffix=" ports"),
            BulkEditField("nic_25g", "25G NICs", "int", suffix=" ports"),
        ]
        dialog = BulkEditDialog("server", len(servers), fields, parent=self)
        if dialog.exec():
            updates = dialog.get_updates()
            if updates:
                self.service.bulk_set_server_fields(servers, updates)

    def _add_server(self):
        dialog = ServerDialog(sites=self.service.project.site_names, clusters=self.service.project.clusters, parent=self)
        if dialog.exec():
            self.service.add_servers(dialog.get_servers())

    def _edit_server(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one server in the table.")
            return

        row = rows[0]
        server = self.model.server_at(row)
        dialog = ServerDialog(server, sites=self.service.project.site_names, clusters=self.service.project.clusters, parent=self)
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
            new_servers = csv_io.import_servers(path)
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
            return
        choice = confirm_import_conflict(
            self, "server", len(self.service.project.servers), len(new_servers),
        )
        if choice == ImportConflictChoice.CANCEL:
            return
        try:
            count = self.service.import_servers_csv(path, replace=choice == ImportConflictChoice.REPLACE)
            QMessageBox.information(self, "Import", f"Imported {count} server(s).")
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

        self.cluster_model.set_clusters(self.service.project.clusters)
        self.cluster_table.auto_size_columns()

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

    # ------------------------------------------------------------------
    # Clusters - CRUD
    # ------------------------------------------------------------------

    def _selected_clusters(self) -> list:
        return [self.cluster_model.cluster_at(row) for row in self.cluster_table.selected_rows()]

    def _add_cluster(self):
        existing_count = len(self.service.project.clusters)
        from src.models.cluster import DEFAULT_CLUSTER_COLORS
        default_color = DEFAULT_CLUSTER_COLORS[existing_count % len(DEFAULT_CLUSTER_COLORS)]
        dialog = ClusterDialog(sites=self.service.project.site_names, default_color=default_color, parent=self)
        if dialog.exec():
            self.service.add_cluster(dialog.get_cluster())

    def _edit_cluster(self):
        rows = self.cluster_table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one cluster in the table.")
            return
        row = rows[0]
        cluster = self.cluster_model.cluster_at(row)
        dialog = ClusterDialog(cluster, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.update_cluster(row, dialog.get_cluster())

    def _delete_clusters(self):
        clusters = self._selected_clusters()
        if not clusters:
            QMessageBox.information(self, "Delete", "Select at least one cluster in the table.")
            return
        confirm = QMessageBox.question(
            self, "Delete",
            f"Delete {len(clusters)} cluster(s)? Any server/VM assigned to one of them "
            "will be unassigned (not deleted). You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_clusters(clusters)

    def _clear_clusters(self):
        if not self.service.project.clusters:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.clusters)} cluster(s)? Any server/VM "
            "assigned to one of them will be unassigned (not deleted). You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_clusters()
