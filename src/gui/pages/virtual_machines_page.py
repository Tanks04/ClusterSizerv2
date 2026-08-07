from pathlib import Path

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

from ..dialogs.vm_dialog import VMDialog
from ..dialogs.import_wizard_dialog import ImportWizardDialog
from ..models.vm_table_model import VMTableModel
from ..widgets.summary_widget import SummaryWidget
from ..widgets.multi_select_table import MultiSelectTableView


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

        clear_action = QAction("🧹 Clear All", self)
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        main_layout.addWidget(toolbar)

        self.table = MultiSelectTableView()
        self.table.set_source_model(self.model)
        self.table.edit_requested.connect(self._edit_vm)
        self.table.delete_requested.connect(self._delete_selected)
        self.table.copy_requested.connect(self._duplicate_selected)

        main_layout.addWidget(self.table)

        summary_layout = QHBoxLayout()

        self.card_vms = SummaryWidget("VMs", "0")
        self.card_vcpu = SummaryWidget("vCPU Demand (Powered On)", "0")
        self.card_ram = SummaryWidget("RAM Demand (Powered On)", "0 GB")
        self.card_cpu_ratio = SummaryWidget("CPU Oversub.", "-")
        self.card_ram_ratio = SummaryWidget("RAM Oversub.", "-")
        self.card_dr_protected = SummaryWidget("DR Protected", "0")

        for card in (
            self.card_vms, self.card_vcpu, self.card_ram,
            self.card_cpu_ratio, self.card_ram_ratio, self.card_dr_protected,
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

        import copy
        import uuid

        for vm in vms:
            new_vm = copy.deepcopy(vm)
            new_vm.uid = str(uuid.uuid4())
            new_vm.name = f"{new_vm.name} (copy)" if new_vm.name else new_vm.name
            self.service.add_vm(new_vm)

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
            QMessageBox.critical(self, "Import Error", str(exc))

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

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export VMs CSV", "vms.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.export_vms_csv(path)
            QMessageBox.information(self, "Export", "VMs exported.")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _clear_all(self):
        if not self.service.project.vms:
            return
        confirm = QMessageBox.question(
            self, "Clear All",
            f"Delete ALL {len(self.service.project.vms)} VM(s)? This cannot be undone.",
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
        ram_ratio = project.ram_oversubscription_ratio("Primary")

        self.card_cpu_ratio.set_value(
            f"{cpu_ratio:.1f} : 1" if cpu_ratio is not None else "-"
        )
        self.card_ram_ratio.set_value(
            f"{ram_ratio * 100:.0f} %" if ram_ratio is not None else "-"
        )
        self.card_dr_protected.set_value(project.dr_protected_vm_count())
