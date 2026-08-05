from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
)

from src.models.virtual_machine import VirtualMachine


class VMDialog(QDialog):

    def __init__(self, vm: VirtualMachine | None = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Virtual Machine")

        self.resize(400, 480)

        outer = QVBoxLayout(self)

        layout = QFormLayout()
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vcpu_spin = QSpinBox()
        self.vcpu_spin.setRange(1, 512)
        self.vcpu_spin.setValue(2)
        self.vcpu_spin.valueChanged.connect(self._sync_dr_defaults)
        layout.addRow("vCPU", self.vcpu_spin)

        self.ram_spin = QDoubleSpinBox()
        self.ram_spin.setDecimals(1)
        self.ram_spin.setRange(0.5, 16384.0)
        self.ram_spin.setSuffix(" GB")
        self.ram_spin.setValue(8.0)
        self.ram_spin.valueChanged.connect(self._sync_dr_defaults)
        layout.addRow("RAM", self.ram_spin)

        self.disk_spin = QDoubleSpinBox()
        self.disk_spin.setDecimals(1)
        self.disk_spin.setRange(1.0, 1000000.0)
        self.disk_spin.setSuffix(" GB")
        self.disk_spin.setValue(100.0)
        self.disk_spin.valueChanged.connect(self._sync_dr_defaults)
        layout.addRow("Disk", self.disk_spin)

        self.powered_check = QCheckBox("Powered on")
        self.powered_check.setChecked(True)
        layout.addRow("", self.powered_check)

        #
        # DR protection - VMs are often NOT replicated 1:1 to DR, so the
        # DR footprint is deliberately kept separate from the Primary one.
        #

        self.dr_check = QCheckBox("DR Protected (replicates to DR)")
        self.dr_check.toggled.connect(self._on_dr_toggled)
        layout.addRow("", self.dr_check)

        self.dr_box = QGroupBox("DR footprint (how much to RESERVE on DR)")
        dr_form = QFormLayout(self.dr_box)

        self.dr_vcpu_spin = QSpinBox()
        self.dr_vcpu_spin.setRange(1, 512)
        dr_form.addRow("DR vCPU", self.dr_vcpu_spin)

        self.dr_ram_spin = QDoubleSpinBox()
        self.dr_ram_spin.setDecimals(1)
        self.dr_ram_spin.setRange(0.5, 16384.0)
        self.dr_ram_spin.setSuffix(" GB")
        dr_form.addRow("DR RAM", self.dr_ram_spin)

        self.dr_disk_spin = QDoubleSpinBox()
        self.dr_disk_spin.setDecimals(1)
        self.dr_disk_spin.setRange(1.0, 1000000.0)
        self.dr_disk_spin.setSuffix(" GB")
        dr_form.addRow("DR Disk", self.dr_disk_spin)

        self.dr_box.setEnabled(False)
        outer.addWidget(self.dr_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._uid = None
        self._dr_manually_edited = False
        self.dr_vcpu_spin.valueChanged.connect(self._mark_dr_manual)
        self.dr_ram_spin.valueChanged.connect(self._mark_dr_manual)
        self.dr_disk_spin.valueChanged.connect(self._mark_dr_manual)

        if vm is not None:
            self.load(vm)
        else:
            self._sync_dr_defaults()

    def _mark_dr_manual(self) -> None:
        self._dr_manually_edited = True

    def _sync_dr_defaults(self) -> None:
        """Until the user manually touches the DR fields, keep them synced
        with the Primary values - most VMs are replicated 1:1 anyway, this
        is just a practical default that's easy to change."""
        if self._dr_manually_edited:
            return
        self.dr_vcpu_spin.blockSignals(True)
        self.dr_ram_spin.blockSignals(True)
        self.dr_disk_spin.blockSignals(True)
        self.dr_vcpu_spin.setValue(self.vcpu_spin.value())
        self.dr_ram_spin.setValue(self.ram_spin.value())
        self.dr_disk_spin.setValue(self.disk_spin.value())
        self.dr_vcpu_spin.blockSignals(False)
        self.dr_ram_spin.blockSignals(False)
        self.dr_disk_spin.blockSignals(False)

    def _on_dr_toggled(self, checked: bool) -> None:
        self.dr_box.setEnabled(checked)

    def load(self, vm: VirtualMachine) -> None:
        self._uid = vm.uid
        self.name_edit.setText(vm.name)
        self.site_combo.setCurrentText(vm.site)
        self.vcpu_spin.setValue(vm.vcpu)
        self.ram_spin.setValue(vm.ram_gb)
        self.disk_spin.setValue(vm.disk_gb)
        self.powered_check.setChecked(vm.powered_on)

        self.dr_check.setChecked(vm.dr_protected)
        self.dr_box.setEnabled(vm.dr_protected)

        self._dr_manually_edited = True  # don't overwrite existing values
        self.dr_vcpu_spin.setValue(vm.dr_vcpu or vm.vcpu)
        self.dr_ram_spin.setValue(vm.dr_ram_gb or vm.ram_gb)
        self.dr_disk_spin.setValue(vm.dr_disk_gb or vm.disk_gb)

    def get_vm(self) -> VirtualMachine:
        vm = VirtualMachine.create_default()

        if self._uid:
            vm.uid = self._uid

        vm.name = self.name_edit.text()
        vm.site = self.site_combo.currentText()
        vm.vcpu = self.vcpu_spin.value()
        vm.ram_gb = self.ram_spin.value()
        vm.disk_gb = self.disk_spin.value()
        vm.powered_on = self.powered_check.isChecked()

        vm.dr_protected = self.dr_check.isChecked()
        vm.dr_vcpu = self.dr_vcpu_spin.value()
        vm.dr_ram_gb = self.dr_ram_spin.value()
        vm.dr_disk_gb = self.dr_disk_spin.value()

        return vm
