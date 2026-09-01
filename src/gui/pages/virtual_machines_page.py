import copy
import uuid
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.services.project_service import ProjectService
from src.persistence.csv_io import CsvSchemaError
from src.persistence import csv_io
from src.gui.import_conflict import confirm_import_conflict, ImportConflictChoice
from src.models.workload_tier import WORKLOAD_TIER_NAMES

from src.gui.dialogs.vm_dialog import VMDialog
from src.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
from src.gui.dialogs.failover_assignment_dialog import FailoverAssignmentDialog
from src.models.failover_assignment import FailoverAssignment
from src.gui.models.vm_table_model import VMTableModel
from src.gui.models.failover_assignment_table_model import FailoverAssignmentTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class VirtualMachinesPage(QWidget):

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = VMTableModel(
            on_change=self.service.touch_vms,
            vlans_provider=lambda: self.service.project.vlans,
            failover_assignments_provider=lambda: self.service.project.failover_assignments,
            clusters_provider=lambda: self.service.project.clusters,
        )
        self.failover_model = FailoverAssignmentTableModel(
            vms_provider=lambda: self.service.project.vms,
        )

        self._create_ui()

        # Not just vms_changed - the CPU Oversub. card depends on Server
        # data too (physical cores, HT, enabled/disabled), so a
        # Servers-only change (e.g. toggling HT, re-enabling a disabled
        # host) must also refresh this page, or the card goes stale
        # while Summary (which listens to the general "changed" signal)
        # correctly shows the current number.
        self.service.changed.connect(self.refresh)
        self.refresh()

    def _create_ui(self):

        main_layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Add", self)
        add_action.triggered.connect(self._add_vm)
        toolbar.addAction(add_action)

        edit_action = QAction("✏ Edit", self)
        edit_action.triggered.connect(self._edit_vm)
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

        smart_import_action = QAction("🧙 Smart Import (any export)", self)
        smart_import_action.setToolTip(
            "Import a VMware/Nutanix/Proxmox/RVTools export (CSV, XLSX, or "
            "JSON) by mapping its columns - works even if it's not our exact "
            "CSV format."
        )
        smart_import_action.triggered.connect(self._smart_import)
        toolbar.addAction(smart_import_action)

        export_action = QAction("📤 Export CSV", self)
        export_action.triggered.connect(self._export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        self.cluster_prep_action = QAction("🧮 Cluster Preparation", self)
        self.cluster_prep_action.setToolTip(
            "Estimate how many hosts to buy, based on these VMs. Disabled "
            "until there's at least one VM to size against."
        )
        self.cluster_prep_action.triggered.connect(self._open_cluster_preparation)
        self.cluster_prep_action.setEnabled(False)
        toolbar.addAction(self.cluster_prep_action)

        toolbar.addSeparator()

        clear_action = QAction("🧹 Clear All", self)
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        main_layout.addWidget(toolbar)

        bulk_row = QHBoxLayout()

        set_tier_label = QLabel("Set Tier:")
        set_tier_label.setToolTip("Sets the Workload Tier used for CPU oversubscription math.")
        bulk_row.addWidget(set_tier_label)

        self.bulk_tier_combo = QComboBox()
        self.bulk_tier_combo.addItems(WORKLOAD_TIER_NAMES)
        bulk_row.addWidget(self.bulk_tier_combo)

        bulk_tier_selected_button = QPushButton("Selected")
        bulk_tier_selected_button.setToolTip("Sets the Workload Tier on the SELECTED VM(s) only - one undo step.")
        bulk_tier_selected_button.clicked.connect(self._set_workload_tier_for_selected)
        bulk_row.addWidget(bulk_tier_selected_button)

        bulk_tier_all_button = QPushButton("All")
        bulk_tier_all_button.setToolTip("Sets the Workload Tier on EVERY VM at once - one undo step, adjust individually afterward if needed.")
        bulk_tier_all_button.clicked.connect(self._set_all_workload_tier)
        bulk_row.addWidget(bulk_tier_all_button)

        bulk_row.addSpacing(16)

        set_failover_label = QLabel("Set failover:")
        set_failover_label.setToolTip("Creates or removes a Failover Assignment to the chosen site.")
        bulk_row.addWidget(set_failover_label)

        self.bulk_failover_site_combo = QComboBox()
        bulk_row.addWidget(self.bulk_failover_site_combo)

        self.bulk_failover_action_combo = QComboBox()
        self.bulk_failover_action_combo.addItem("Add", userData=True)
        self.bulk_failover_action_combo.addItem("Remove", userData=False)
        self.bulk_failover_action_combo.setToolTip(
            "Add = create a Failover Assignment to the chosen site. Remove = delete "
            "an existing one, if there is one. Choose which, then click Selected/All."
        )
        bulk_row.addWidget(self.bulk_failover_action_combo)

        bulk_failover_selected_button = QPushButton("Selected")
        bulk_failover_selected_button.setToolTip(
            "Applies the chosen Add/Remove action to the SELECTED VM(s) only - one "
            "undo step. Manage individual footprint numbers (vCPU/RAM/disk per "
            "site) in the Failover Assignments table below."
        )
        bulk_failover_selected_button.clicked.connect(self._set_failover_for_selected_from_checkbox)
        bulk_row.addWidget(bulk_failover_selected_button)

        bulk_failover_all_button = QPushButton("All")
        bulk_failover_all_button.setToolTip("Applies the chosen Add/Remove action to EVERY VM at once - one undo step.")
        bulk_failover_all_button.clicked.connect(self._set_failover_for_all_from_checkbox)
        bulk_row.addWidget(bulk_failover_all_button)

        bulk_row.addStretch()
        main_layout.addLayout(bulk_row)

        move_row = QHBoxLayout()

        site_label = QLabel("Bulk move site:")
        site_label.setToolTip(
            "Relocates the VM to a different site - separate from DR Protected/"
            "Failover Assignment, which just flags a VM as replicated while it "
            "stays on its current site."
        )
        move_row.addWidget(site_label)

        self.bulk_site_combo = QComboBox()
        move_row.addWidget(self.bulk_site_combo)

        bulk_site_selected_button = QPushButton("Selected")
        bulk_site_selected_button.setToolTip("Moves the SELECTED VM(s) to the chosen site - one undo step. Same as right-click \u2192 Move to Primary/DR.")
        bulk_site_selected_button.clicked.connect(self._set_site_for_selected_from_combo)
        move_row.addWidget(bulk_site_selected_button)

        bulk_site_all_button = QPushButton("All")
        bulk_site_all_button.setToolTip("Moves EVERY VM to the chosen site at once - one undo step.")
        bulk_site_all_button.clicked.connect(self._set_all_vms_site)
        move_row.addWidget(bulk_site_all_button)

        move_row.addSpacing(16)

        cluster_label = QLabel("Bulk move Cluster:")
        cluster_label.setToolTip(
            "Assigns the VM to an isolated cluster (e.g. a separate vSphere/"
            "Nutanix/Proxmox/Hyper-V cluster at the same site) - manage the list "
            "of Clusters on the Servers tab."
        )
        move_row.addWidget(cluster_label)

        self.bulk_cluster_combo = QComboBox()
        move_row.addWidget(self.bulk_cluster_combo)

        bulk_cluster_selected_button = QPushButton("Selected")
        bulk_cluster_selected_button.setToolTip(
            "Assigns the SELECTED VM(s) to the chosen cluster - one undo step. "
            "Same as right-click \u2192 Add to Cluster."
        )
        bulk_cluster_selected_button.clicked.connect(self._set_cluster_for_selected_from_combo)
        move_row.addWidget(bulk_cluster_selected_button)

        bulk_cluster_all_button = QPushButton("All")
        bulk_cluster_all_button.setToolTip("Assigns EVERY VM to the chosen cluster at once - one undo step.")
        bulk_cluster_all_button.clicked.connect(self._set_all_vms_cluster)
        move_row.addWidget(bulk_cluster_all_button)

        move_row.addStretch()
        main_layout.addLayout(move_row)

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_vm)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)
        self.table.set_custom_actions([])  # populated dynamically in refresh() - site list can change

        main_layout.addWidget(self.table)

        summary_layout = QHBoxLayout()

        self.card_vms = SummaryWidget("VMs", "0")
        self.card_vcpu = SummaryWidget("vCPU Demand (Powered On)", "0")
        self.card_ram = SummaryWidget("RAM Demand (Powered On)", "0 GB")
        self.card_cpu_ratio = SummaryWidget("CPU Oversub.", "-")
        self.card_vm_storage = SummaryWidget("VM Storage", "0 GB")
        self.card_failover_assigned = SummaryWidget("Failover Assigned", "0")

        for card in (
            self.card_vms, self.card_vcpu, self.card_ram,
            self.card_vm_storage, self.card_cpu_ratio, self.card_failover_assigned,
        ):
            summary_layout.addWidget(card)

        main_layout.addLayout(summary_layout)

        #
        # Failover Assignments - standalone list (VM -> target site,
        # own vCPU/RAM/disk footprint per row) - see FailoverAssignment's
        # docstring for why this isn't a field on the VM itself. One VM
        # can appear in several rows here, once per target site.
        #

        failover_box = QGroupBox("Failover Assignments")
        failover_layout = QVBoxLayout(failover_box)

        failover_toolbar = QToolBar()
        failover_toolbar.setMovable(False)

        add_failover_action = QAction("➕ Add", self)
        add_failover_action.triggered.connect(self._add_failover_assignment)
        failover_toolbar.addAction(add_failover_action)

        edit_failover_action = QAction("✏ Edit", self)
        edit_failover_action.triggered.connect(self._edit_failover_assignment)
        failover_toolbar.addAction(edit_failover_action)

        delete_failover_action = QAction("🗑 Delete", self)
        delete_failover_action.triggered.connect(self._delete_failover_assignments)
        failover_toolbar.addAction(delete_failover_action)

        failover_toolbar.addSeparator()

        clear_failover_action = QAction("🧹 Clear All", self)
        clear_failover_action.triggered.connect(self._clear_failover_assignments)
        failover_toolbar.addAction(clear_failover_action)

        failover_layout.addWidget(failover_toolbar)

        self.failover_table = MultiSelectTableView()
        self.failover_table.set_source_model(self.failover_model)
        self.failover_table.edit_requested.connect(self._edit_failover_assignment)
        self.failover_table.delete_requested.connect(self._delete_failover_assignments)
        self.failover_table.set_custom_actions([
            ("\u2705 Acknowledge (footprint is intentional)",
             lambda checked=False: self._set_failover_confirmed_for_selected(True)),
            ("Un-acknowledge",
             lambda checked=False: self._set_failover_confirmed_for_selected(False)),
        ])

        failover_layout.addWidget(self.failover_table)

        main_layout.addWidget(failover_box)

    def _selected_vms(self) -> list:
        return [self.model.vm_at(row) for row in self.table.selected_rows()]

    def _add_vm(self):
        dialog = VMDialog(vlans=self.service.project.vlans, storages=self.service.project.storages, clusters=self.service.project.clusters, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.add_vm(dialog.get_vm())

    def _edit_vm(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one VM in the table.")
            return

        row = rows[0]
        vm = self.model.vm_at(row)
        dialog = VMDialog(vm, vlans=self.service.project.vlans, storages=self.service.project.storages, clusters=self.service.project.clusters, sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            self.service.update_vm(row, dialog.get_vm())

    def _delete_selected(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Delete", "Select at least one VM in the table.")
            return

        confirm = QMessageBox.question(self, "Delete", f"Delete {len(vms)} VM(s)?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_vms(vms)

    def _duplicate_selected(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Copy", "Select at least one VM in the table.")
            return

        copies = []
        for vm in vms:
            new_vm = copy.deepcopy(vm)
            new_vm.uid = str(uuid.uuid4())
            new_vm.name = f"{new_vm.name} (copy)" if new_vm.name else new_vm.name
            copies.append(new_vm)

        self.service.add_vms(copies)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import VMs CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            new_vms = csv_io.import_vms(path)
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
            return
        choice = confirm_import_conflict(
            self, "VM", len(self.service.project.vms), len(new_vms),
        )
        if choice == ImportConflictChoice.CANCEL:
            return
        try:
            count = self.service.import_vms_csv(path, replace=choice == ImportConflictChoice.REPLACE)
            QMessageBox.information(self, "Import", f"Imported {count} VM(s).")
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _smart_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Smart Import - choose export file", "",
            "Supported files (*.csv *.xlsx *.xlsm *.json);;All files (*)",
        )
        if not path:
            return

        dialog = ImportWizardDialog(Path(path), sites=self.service.project.site_names, parent=self)
        if dialog.exec():
            vms = dialog.get_imported_vms()
            if vms:
                choice = confirm_import_conflict(
                    self, "VM", len(self.service.project.vms), len(vms),
                )
                if choice == ImportConflictChoice.CANCEL:
                    return
                self.service.add_vms(vms, replace=choice == ImportConflictChoice.REPLACE)
                skipped = dialog.get_skipped_count()
                msg = f"Imported {len(vms)} VM(s)."
                if skipped:
                    msg += f" ({skipped} skipped by the profile's name filter.)"
                QMessageBox.information(self, "Smart Import", msg)

    def _open_cluster_preparation(self):
        dialog = ClusterPreparationWizard(self.service.project, parent=self)
        dialog.exec()

        self._apply_cluster_prep_site(
            "Primary", dialog.new_primary_servers, dialog.new_primary_storage,
        )
        self._apply_cluster_prep_site(
            "DR", dialog.new_dr_servers, dialog.new_dr_storage,
        )
        for site, (servers, storages) in dialog.new_site_clusters.items():
            self._apply_cluster_prep_site(site, servers, storages)

        for assignment in dialog.new_failover_assignments:
            self.service.add_failover_assignment(assignment)

        if dialog.new_backup_destinations:
            self.service.add_backup_destinations(dialog.new_backup_destinations)

    def _apply_cluster_prep_site(self, site: str, servers: list, storages: list) -> None:
        if not servers and not storages:
            return

        existing = [s for s in self.service.project.servers if s.site == site] + \
                   [s for s in self.service.project.storages if s.site == site]

        if existing:
            reply = QMessageBox.question(
                self, "Cluster Preparation",
                f"{site} already has {len(existing)} server/storage entrie(s). "
                f"Add the {len(servers)} recommended server(s) and "
                f"{len(storages)} storage system(s) to the existing ones, or "
                "replace them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            # Yes = Add, No = Replace, Cancel = do nothing - QMessageBox.question
            # doesn't support custom button labels here without more setup, so
            # the choice is spelled out in the question text above.
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.No:
                self.service.replace_servers_and_storages_at_site(site, servers, storages)
                QMessageBox.information(
                    self, "Cluster Preparation",
                    f"Replaced {site} servers/storage with {len(servers)} server(s) "
                    f"and {len(storages)} storage system(s).",
                )
                return

        self.service.add_servers_and_storages(servers, storages)
        QMessageBox.information(
            self, "Cluster Preparation",
            f"{len(servers)} {site} server(s) and {len(storages)} storage "
            "system(s) added - review and adjust the specs there.",
        )

    def _set_all_workload_tier(self):
        if not self.service.project.vms:
            return
        tier = self.bulk_tier_combo.currentText()
        self.service.set_all_vms_workload_tier(tier)

    def _set_failover_for_all_from_checkbox(self):
        if not self.service.project.vms:
            return
        site = self.bulk_failover_site_combo.currentText()
        if not site:
            return
        self.service.set_failover_assignment_for_all_vms(site, self.bulk_failover_action_combo.currentData())

    def _set_workload_tier_for_selected(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Set Workload Tier", "Select at least one VM in the table.")
            return
        tier = self.bulk_tier_combo.currentText()
        self.service.set_workload_tier_for_vms(vms, tier)

    def _set_failover_for_selected_from_checkbox(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Failover Assignment", "Select at least one VM in the table.")
            return
        site = self.bulk_failover_site_combo.currentText()
        if not site:
            return
        assigned = self.bulk_failover_action_combo.currentData()
        verb = f"assigned to fail over to {site}" if assigned else f"un-assigned from {site}"
        reply = QMessageBox.question(
            self, "Failover Assignment",
            f"{len(vms)} selected VM(s) will be {verb}. Continue?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.set_failover_assignment_for_vms(vms, site, assigned)

    def _set_all_vms_site(self):
        if not self.service.project.vms:
            return
        site = self.bulk_site_combo.currentText()
        reply = QMessageBox.question(
            self, "Set Site",
            f"Move ALL {len(self.service.project.vms)} VM(s) to {site}?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.set_site_for_vms(self.service.project.vms, site)

    def _set_cluster_for_selected_from_combo(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Move to Cluster", "Select at least one VM in the table.")
            return
        cluster_uid = self.bulk_cluster_combo.currentData()
        if not cluster_uid:
            QMessageBox.information(self, "Move to Cluster", "Add a Cluster first (Servers tab).")
            return
        self.service.bulk_set_vm_fields(vms, {"cluster_uid": cluster_uid})

    def _set_all_vms_cluster(self):
        if not self.service.project.vms:
            return
        cluster_uid = self.bulk_cluster_combo.currentData()
        if not cluster_uid:
            QMessageBox.information(self, "Move to Cluster", "Add a Cluster first (Servers tab).")
            return
        cluster_name = self.bulk_cluster_combo.currentText()
        reply = QMessageBox.question(
            self, "Move to Cluster",
            f"Assign ALL {len(self.service.project.vms)} VM(s) to {cluster_name}?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.bulk_set_vm_fields(self.service.project.vms, {"cluster_uid": cluster_uid})

    def _add_selected_to_cluster(self, cluster_uid: str):
        vms = self._selected_vms()
        if not vms:
            return
        self.service.bulk_set_vm_fields(vms, {"cluster_uid": cluster_uid})

    def _assign_selected_to_failover(self, site: str):
        vms = self._selected_vms()
        if not vms:
            return
        assignments = []
        for vm in vms:
            assignment = FailoverAssignment.create_default()
            assignment.vm_uid = vm.uid
            assignment.target_site = site
            assignment.vcpu = vm.vcpu
            assignment.ram_gb = vm.ram_gb
            assignment.disk_gb = vm.disk_gb
            assignments.append(assignment)
        self.service.add_failover_assignments(assignments)
        QMessageBox.information(
            self, "Assign to Failover",
            f"{len(assignments)} VM(s) assigned to fail over to {site}, each defaulting "
            "to its own current vCPU/RAM/disk - adjust individually in the Failover "
            "Assignments table below if needed.",
        )

    def _set_site_for_selected_from_combo(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Set Site", "Select at least one VM in the table.")
            return
        self._set_site_for_selected(self.bulk_site_combo.currentText(), vms=vms)

    def _set_site_for_selected(self, site: str, vms: list | None = None):
        if vms is None:
            vms = self._selected_vms()
        if not vms:
            return
        reply = QMessageBox.question(
            self, "Set Site",
            f"Move {len(vms)} selected VM(s) to {site}? This relocates where the "
            "VM lives - it's separate from DR Protected (which just flags a VM "
            "as replicated while it stays on its current site).",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.set_site_for_vms(vms, site)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export VMs CSV", "vms.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_vms_csv(path)
            QMessageBox.information(self, "Export", "VMs exported.")
        except Exception as exc:
            report_error(self, "Export Error", exc)

    def _clear_all(self):
        if not self.service.project.vms:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.vms)} VM(s)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_vms()

    def refresh(self):
        self.model.set_vms(self.service.project.vms)
        self.table.auto_size_columns()

        project = self.service.project

        self.card_vms.set_value(len(project.vms))
        self.card_vcpu.set_value(
            sum(project.vm_vcpu_demand(site) for site in project.site_names)
        )
        self.card_ram.set_value(
            f"{sum(project.vm_ram_demand_gb(site) for site in project.site_names):.0f} GB"
        )

        cpu_ratio = project.cpu_oversubscription_ratio("Primary")

        self.card_cpu_ratio.set_value(
            f"{cpu_ratio:.1f} : 1" if cpu_ratio is not None else "-"
        )
        total_vm_storage_gb = sum(project.vm_disk_demand_gb(site) for site in project.site_names)
        if total_vm_storage_gb >= 1024:
            self.card_vm_storage.set_value(f"{total_vm_storage_gb / 1024:.1f} TB")
        else:
            self.card_vm_storage.set_value(f"{total_vm_storage_gb:.0f} GB")

        assigned_vm_uids = {a.vm_uid for a in project.failover_assignments}
        self.card_failover_assigned.set_value(len(assigned_vm_uids))

        self.failover_model.set_assignments(project.failover_assignments)
        self.failover_table.auto_size_columns()

        self._refresh_site_combos(project.site_names)
        self._refresh_cluster_combo(project.clusters)
        self._refresh_custom_actions(project.site_names, project.clusters)

        self.cluster_prep_action.setEnabled(len(project.vms) > 0)

    def _refresh_site_combos(self, site_names: list[str]) -> None:
        """The dropdowns are rebuilt only when the site list itself has
        changed, preserving the current selection where possible -
        rebuilding on every refresh would reset the user's choice mid-task."""
        for combo in (self.bulk_site_combo, self.bulk_failover_site_combo):
            current = combo.currentText()
            existing = [combo.itemText(i) for i in range(combo.count())]
            if existing == site_names:
                continue
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(site_names)
            if current in site_names:
                combo.setCurrentText(current)
            combo.blockSignals(False)

    def _refresh_cluster_combo(self, clusters: list) -> None:
        current_uid = self.bulk_cluster_combo.currentData()
        existing_uids = [self.bulk_cluster_combo.itemData(i) for i in range(self.bulk_cluster_combo.count())]
        new_uids = [c.uid for c in clusters]
        if existing_uids == new_uids:
            return
        self.bulk_cluster_combo.blockSignals(True)
        self.bulk_cluster_combo.clear()
        for cluster in clusters:
            self.bulk_cluster_combo.addItem(cluster.name or "(unnamed)", userData=cluster.uid)
        restored = self.bulk_cluster_combo.findData(current_uid)
        if restored >= 0:
            self.bulk_cluster_combo.setCurrentIndex(restored)
        self.bulk_cluster_combo.blockSignals(False)

    def _refresh_custom_actions(self, site_names: list[str], clusters: list | None = None) -> None:
        actions = [
            (f"\U0001f4cd Move to {site}", lambda checked=False, s=site: self._set_site_for_selected(s))
            for site in site_names
        ]
        actions.extend(
            (f"\u2708 Assign to Failover ({site})", lambda checked=False, s=site: self._assign_selected_to_failover(s))
            for site in site_names
        )
        actions.extend(
            (f"\U0001f517 Add to Cluster ({cluster.name or '(unnamed)'})",
             lambda checked=False, uid=cluster.uid: self._add_selected_to_cluster(uid))
            for cluster in (clusters or [])
        )
        self.table.set_custom_actions(actions)

    # ------------------------------------------------------------------
    # Failover Assignments - actions
    # ------------------------------------------------------------------

    def _selected_failover_assignments(self) -> list:
        return [self.failover_model.assignment_at(row) for row in self.failover_table.selected_rows()]

    def _add_failover_assignment(self):
        if not self.service.project.vms:
            QMessageBox.information(self, "Add", "Add at least one VM first.")
            return
        dialog = FailoverAssignmentDialog(
            vms=self.service.project.vms, sites=self.service.project.site_names, parent=self,
        )
        if dialog.exec():
            self.service.add_failover_assignment(dialog.get_assignment())

    def _edit_failover_assignment(self):
        rows = self.failover_table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one assignment in the table.")
            return
        row = rows[0]
        assignment = self.failover_model.assignment_at(row)
        dialog = FailoverAssignmentDialog(
            assignment, vms=self.service.project.vms, sites=self.service.project.site_names, parent=self,
        )
        if dialog.exec():
            self.service.update_failover_assignment(row, dialog.get_assignment())

    def _delete_failover_assignments(self):
        assignments = self._selected_failover_assignments()
        if not assignments:
            QMessageBox.information(self, "Delete", "Select at least one assignment in the table.")
            return
        confirm = QMessageBox.question(
            self, "Delete",
            f"Delete {len(assignments)} failover assignment(s)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.remove_failover_assignments(assignments)

    def _clear_failover_assignments(self):
        if not self.service.project.failover_assignments:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.failover_assignments)} failover "
            "assignment(s)? You can undo with Ctrl+Z.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.service.clear_failover_assignments()

    def _set_failover_confirmed_for_selected(self, confirmed: bool):
        assignments = self._selected_failover_assignments()
        if not assignments:
            QMessageBox.information(self, "Acknowledge", "Select at least one assignment in the table.")
            return
        self.service.set_failover_assignment_confirmed(assignments, confirmed)
