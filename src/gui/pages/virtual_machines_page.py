import copy
import uuid
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
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
from src.models.workload_tier import WORKLOAD_TIER_NAMES

from src.gui.dialogs.vm_dialog import VMDialog
from src.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
from src.gui.models.vm_table_model import VMTableModel
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.multi_select_table import MultiSelectTableView
from src.gui.error_handling import report_error


class VirtualMachinesPage(QWidget):

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.model = VMTableModel(on_change=self.service.touch_vms)

        self._create_ui()

        self.service.vms_changed.connect(self.refresh)
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
        bulk_row.addWidget(QLabel("Bulk edit:"))

        self.bulk_tier_combo = QComboBox()
        self.bulk_tier_combo.addItems(WORKLOAD_TIER_NAMES)
        bulk_row.addWidget(self.bulk_tier_combo)

        bulk_tier_selected_button = QPushButton("Set Tier (Selected)")
        bulk_tier_selected_button.setToolTip("Sets the Workload Tier on the SELECTED VM(s) only - one undo step.")
        bulk_tier_selected_button.clicked.connect(self._set_workload_tier_for_selected)
        bulk_row.addWidget(bulk_tier_selected_button)

        bulk_tier_all_button = QPushButton("Set Tier (All)")
        bulk_tier_all_button.setToolTip("Sets the Workload Tier on EVERY VM at once - one undo step, adjust individually afterward if needed.")
        bulk_tier_all_button.clicked.connect(self._set_all_workload_tier)
        bulk_row.addWidget(bulk_tier_all_button)

        bulk_row.addSpacing(16)

        self.bulk_dr_check = QCheckBox("DR Protected")
        bulk_row.addWidget(self.bulk_dr_check)

        bulk_dr_selected_button = QPushButton("Apply (Selected)")
        bulk_dr_selected_button.setToolTip("Sets DR Protected on the SELECTED VM(s) only - one undo step. Same as right-click \u2192 Mark/Un-mark DR Protected on the table.")
        bulk_dr_selected_button.clicked.connect(self._set_dr_protected_for_selected_from_checkbox)
        bulk_row.addWidget(bulk_dr_selected_button)

        bulk_dr_all_button = QPushButton("Apply (All)")
        bulk_dr_all_button.setToolTip("Sets DR Protected on EVERY VM at once - one undo step.")
        bulk_dr_all_button.clicked.connect(self._set_all_dr_protected)
        bulk_row.addWidget(bulk_dr_all_button)

        bulk_row.addStretch()
        main_layout.addLayout(bulk_row)

        site_row = QHBoxLayout()
        site_row.addWidget(QLabel("Bulk move (Site \u2260 DR Protected - this actually relocates the VM):"))

        self.bulk_site_combo = QComboBox()
        self.bulk_site_combo.addItems(["Primary", "DR"])
        site_row.addWidget(self.bulk_site_combo)

        bulk_site_selected_button = QPushButton("Set Site (Selected)")
        bulk_site_selected_button.setToolTip("Moves the SELECTED VM(s) to the chosen site - one undo step. Same as right-click \u2192 Move to Primary/DR.")
        bulk_site_selected_button.clicked.connect(self._set_site_for_selected_from_combo)
        site_row.addWidget(bulk_site_selected_button)

        bulk_site_all_button = QPushButton("Set Site (All)")
        bulk_site_all_button.setToolTip("Moves EVERY VM to the chosen site at once - one undo step.")
        bulk_site_all_button.clicked.connect(self._set_all_vms_site)
        site_row.addWidget(bulk_site_all_button)

        site_row.addStretch()
        main_layout.addLayout(site_row)

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_vm)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)
        self.table.set_custom_actions([
            ("\U0001f6e1 Mark DR Protected", lambda: self._set_dr_protected_for_selected(True)),
            ("Un-mark DR Protected", lambda: self._set_dr_protected_for_selected(False)),
            ("\U0001f4cd Move to Primary", lambda: self._set_site_for_selected("Primary")),
            ("\U0001f4cd Move to DR", lambda: self._set_site_for_selected("DR")),
        ])

        main_layout.addWidget(self.table)

        summary_layout = QHBoxLayout()

        self.card_vms = SummaryWidget("VMs", "0")
        self.card_vcpu = SummaryWidget("vCPU Demand (Powered On)", "0")
        self.card_ram = SummaryWidget("RAM Demand (Powered On)", "0 GB")
        self.card_cpu_ratio = SummaryWidget("CPU Oversub.", "-")
        self.card_vm_storage = SummaryWidget("VM Storage", "0 GB")
        self.card_dr_protected = SummaryWidget("DR Protected", "0")

        for card in (
            self.card_vms, self.card_vcpu, self.card_ram,
            self.card_cpu_ratio, self.card_vm_storage, self.card_dr_protected,
        ):
            summary_layout.addWidget(card)

        main_layout.addLayout(summary_layout)

    def _selected_vms(self) -> list:
        return [self.model.vm_at(row) for row in self.table.selected_rows()]

    def _add_vm(self):
        dialog = VMDialog(parent=self)
        if dialog.exec():
            self.service.add_vm(dialog.get_vm())

    def _edit_vm(self):
        rows = self.table.selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "Edit", "Select exactly one VM in the table.")
            return

        row = rows[0]
        vm = self.model.vm_at(row)
        dialog = VMDialog(vm, parent=self)
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
            count = self.service.import_vms_csv(path)
            QMessageBox.information(self, "Import", f"Imported {count} VM(s).")
        except CsvSchemaError as exc:
            QMessageBox.warning(self, "Wrong file", str(exc))
        except Exception as exc:
            report_error(self, "Import Error", exc)

    def _smart_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Smart Import - choose export file", "",
            "Supported files (*.csv *.xlsx *.xlsm *.json);;All files (*)",
        )
        if not path:
            return

        dialog = ImportWizardDialog(Path(path), parent=self)
        if dialog.exec():
            vms = dialog.get_imported_vms()
            if vms:
                self.service.add_vms(vms)
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

    def _set_all_dr_protected(self):
        if not self.service.project.vms:
            return
        self.service.set_all_vms_dr_protected(self.bulk_dr_check.isChecked())

    def _set_workload_tier_for_selected(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "Set Workload Tier", "Select at least one VM in the table.")
            return
        tier = self.bulk_tier_combo.currentText()
        self.service.set_workload_tier_for_vms(vms, tier)

    def _set_dr_protected_for_selected_from_checkbox(self):
        vms = self._selected_vms()
        if not vms:
            QMessageBox.information(self, "DR Protected", "Select at least one VM in the table.")
            return
        self._set_dr_protected_for_selected(self.bulk_dr_check.isChecked(), vms=vms)

    def _set_dr_protected_for_selected(self, protected: bool, vms: list | None = None):
        if vms is None:
            vms = self._selected_vms()
        if not vms:
            return
        verb = "DR Protected" if protected else "NOT DR Protected"
        reply = QMessageBox.question(
            self, "DR Protected",
            f"Mark {len(vms)} selected VM(s) as {verb}?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.set_dr_protected_for_vms(vms, protected)

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
            project.vm_vcpu_demand("Primary") + project.vm_vcpu_demand("DR")
        )
        self.card_ram.set_value(
            f"{project.vm_ram_demand_gb('Primary') + project.vm_ram_demand_gb('DR'):.0f} GB"
        )

        cpu_ratio = project.cpu_oversubscription_ratio("Primary")

        self.card_cpu_ratio.set_value(
            f"{cpu_ratio:.1f} : 1" if cpu_ratio is not None else "-"
        )
        total_vm_storage_gb = project.vm_disk_demand_gb("Primary") + project.vm_disk_demand_gb("DR")
        if total_vm_storage_gb >= 1024:
            self.card_vm_storage.set_value(f"{total_vm_storage_gb / 1024:.1f} TB")
        else:
            self.card_vm_storage.set_value(f"{total_vm_storage_gb:.0f} GB")
        self.card_dr_protected.set_value(project.dr_protected_vm_count())

        self.cluster_prep_action.setEnabled(len(project.vms) > 0)
