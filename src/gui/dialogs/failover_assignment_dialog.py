from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)

from src.models.failover_assignment import FailoverAssignment


class FailoverAssignmentDialog(QDialog):
    """One VM's failover footprint on ONE target site - see
    FailoverAssignment's docstring for why this is a standalone row
    rather than a field on the VM itself."""

    def __init__(
        self,
        assignment: FailoverAssignment | None = None,
        vms: list | None = None,
        sites: list | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._vms = vms or []
        self._sites = sites or ["Primary", "DR"]

        self.setWindowTitle("Failover Assignment")
        self.resize(380, 260)

        layout = QFormLayout(self)

        self.vm_combo = QComboBox()
        for vm in self._vms:
            self.vm_combo.addItem(vm.name or "(unnamed)", userData=vm.uid)
        self.vm_combo.currentIndexChanged.connect(self._on_vm_changed)
        layout.addRow("VM", self.vm_combo)

        self.target_site_combo = QComboBox()
        self.target_site_combo.addItems(self._sites)
        layout.addRow("Target Site", self.target_site_combo)

        self.vcpu_spin = QSpinBox()
        self.vcpu_spin.setRange(0, 512)
        layout.addRow("vCPU", self.vcpu_spin)

        self.ram_spin = QDoubleSpinBox()
        self.ram_spin.setDecimals(1)
        self.ram_spin.setRange(0.0, 16384.0)
        self.ram_spin.setSuffix(" GB")
        layout.addRow("RAM", self.ram_spin)

        self.disk_spin = QDoubleSpinBox()
        self.disk_spin.setDecimals(1)
        self.disk_spin.setRange(0.0, 1000000.0)
        self.disk_spin.setSuffix(" GB")
        layout.addRow("Disk", self.disk_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._uid = None

        if assignment is not None:
            self.load(assignment)
        elif self._vms:
            self._sync_defaults_to_selected_vm()

    def _selected_vm(self):
        vm_uid = self.vm_combo.currentData()
        return next((v for v in self._vms if v.uid == vm_uid), None)

    def _on_vm_changed(self):
        self._sync_defaults_to_selected_vm()

    def _sync_defaults_to_selected_vm(self) -> None:
        """Defaults the footprint to match the VM's own vcpu/ram/disk -
        the common case, easy to override for a smaller failover
        footprint (e.g. a budget DR site)."""
        vm = self._selected_vm()
        if vm is None:
            return
        self.vcpu_spin.setValue(vm.vcpu)
        self.ram_spin.setValue(vm.ram_gb)
        self.disk_spin.setValue(vm.disk_gb)

    def load(self, assignment: FailoverAssignment) -> None:
        self._uid = assignment.uid
        vm_index = self.vm_combo.findData(assignment.vm_uid)
        if vm_index >= 0:
            self.vm_combo.setCurrentIndex(vm_index)
        self.target_site_combo.setCurrentText(assignment.target_site)
        self.vcpu_spin.setValue(assignment.vcpu)
        self.ram_spin.setValue(assignment.ram_gb)
        self.disk_spin.setValue(assignment.disk_gb)

    def get_assignment(self) -> FailoverAssignment:
        assignment = FailoverAssignment.create_default()

        if self._uid:
            assignment.uid = self._uid

        assignment.vm_uid = self.vm_combo.currentData() or ""
        assignment.target_site = self.target_site_combo.currentText()
        assignment.vcpu = self.vcpu_spin.value()
        assignment.ram_gb = self.ram_spin.value()
        assignment.disk_gb = self.disk_spin.value()

        return assignment
