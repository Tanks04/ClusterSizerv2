from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.calculations.thresholds import PRESETS
from src.models.cluster_project import DEPLOYMENT_MODELS
from src.services.project_service import ProjectService


def _ratio_spin(value: float, suffix: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setDecimals(2)
    spin.setRange(0.0, 100.0)
    spin.setSingleStep(0.1)
    spin.setSuffix(suffix)
    spin.setValue(value)
    return spin


class SettingsPage(QWidget):
    """Per-site deployment model (On-Premise/Cloud), applied immediately,
    and warning thresholds for oversubscription calculations, applied on
    'Apply' - shown on the Summary/VMs pages."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()
        self._load_from_service()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Warning thresholds are used to color the status (OK / Warning / "
            "Critical) on the Summary and VMs pages."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        #
        # Deployment model (per-site - hybrid setups like on-prem
        # Primary + cloud DR/DRaaS are common)
        #

        deployment_box = QGroupBox("Deployment Model")
        deployment_form = QFormLayout(deployment_box)

        deployment_note = QLabel(
            "Set per site, not per project - a hybrid setup (e.g. on-premise "
            "Primary with a cloud DR/DRaaS) is common. Currently affects Rack "
            "Sizing on the Summary page and in the Word report - a Cloud site "
            "shows \"Cloud\" instead of trying to sum rack units/power, since "
            "that's not a concept that applies there. Applied immediately."
        )
        deployment_note.setWordWrap(True)
        deployment_note.setStyleSheet("color: #757575; font-style: italic;")
        deployment_form.addRow(deployment_note)

        self.primary_deployment_combo = QComboBox()
        self.primary_deployment_combo.addItems(DEPLOYMENT_MODELS)
        self.primary_deployment_combo.currentTextChanged.connect(
            lambda text: self.service.set_primary_deployment_model(text)
        )
        deployment_form.addRow("Primary Site", self.primary_deployment_combo)

        self.dr_deployment_combo = QComboBox()
        self.dr_deployment_combo.addItems(DEPLOYMENT_MODELS)
        self.dr_deployment_combo.currentTextChanged.connect(
            lambda text: self.service.set_dr_deployment_model(text)
        )
        deployment_form.addRow("DR Site", self.dr_deployment_combo)

        layout.addWidget(deployment_box)

        #
        # Rack Capacity (per site) - how many U are AVAILABLE, separate
        # from Rack Sizing's "how many U are USED by entered equipment"
        #

        rack_capacity_box = QGroupBox("Rack Capacity")
        rack_capacity_form = QFormLayout(rack_capacity_box)

        rack_capacity_note = QLabel(
            "How many rack units are available at each site - separate from "
            "Rack Sizing, which only totals what's been entered on Servers/"
            "Storage/Switches. 0 = not entered (Rack Sizing just shows the "
            "used figure with no \"of how many\" context). DR is often a "
            "smaller rack than Primary in practice, hence per site. Applied "
            "immediately."
        )
        rack_capacity_note.setWordWrap(True)
        rack_capacity_note.setStyleSheet("color: #757575; font-style: italic;")
        rack_capacity_form.addRow(rack_capacity_note)

        self.primary_rack_capacity_spin = QSpinBox()
        self.primary_rack_capacity_spin.setRange(0, 1000)
        self.primary_rack_capacity_spin.setSuffix(" U")
        self.primary_rack_capacity_spin.setSpecialValueText("(not set)")
        self.primary_rack_capacity_spin.valueChanged.connect(
            lambda value: self.service.set_primary_rack_capacity_u(value)
        )
        rack_capacity_form.addRow("Primary Site", self.primary_rack_capacity_spin)

        self.dr_rack_capacity_spin = QSpinBox()
        self.dr_rack_capacity_spin.setRange(0, 1000)
        self.dr_rack_capacity_spin.setSuffix(" U")
        self.dr_rack_capacity_spin.setSpecialValueText("(not set)")
        self.dr_rack_capacity_spin.valueChanged.connect(
            lambda value: self.service.set_dr_rack_capacity_u(value)
        )
        rack_capacity_form.addRow("DR Site", self.dr_rack_capacity_spin)

        layout.addWidget(rack_capacity_box)

        #
        # Recommended presets
        #

        preset_box = QGroupBox("Recommended Presets (by hypervisor)")
        preset_layout = QVBoxLayout(preset_box)

        preset_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        for preset in PRESETS:
            self.preset_combo.addItem(preset.label, preset.key)
        self.preset_combo.currentIndexChanged.connect(self._update_preset_description)
        preset_row.addWidget(self.preset_combo)

        apply_preset_button = QPushButton("Use This Preset")
        apply_preset_button.clicked.connect(self._use_preset)
        preset_row.addWidget(apply_preset_button)

        preset_layout.addLayout(preset_row)

        self.preset_description_label = QLabel("")
        self.preset_description_label.setWordWrap(True)
        self.preset_description_label.setStyleSheet("color: #757575; font-style: italic;")
        preset_layout.addWidget(self.preset_description_label)

        self.preset_status_label = QLabel("")
        self.preset_status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        preset_layout.addWidget(self.preset_status_label)

        note = QLabel(
            "These are commonly-cited starting points, not official vendor "
            "guarantees - actual safe ratios always depend on your workload "
            "mix. \"Use This Preset\" only fills in the fields below; click "
            "\"Apply\" to actually save."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #757575; font-style: italic;")
        preset_layout.addWidget(note)

        layout.addWidget(preset_box)
        self._update_preset_description()

        #
        # Manual thresholds
        #

        cpu_box = QGroupBox("CPU Oversubscription (vCPU : physical core)")
        cpu_form = QFormLayout(cpu_box)
        self.cpu_warning_spin = _ratio_spin(4.0, " : 1")
        self.cpu_critical_spin = _ratio_spin(6.0, " : 1")
        cpu_form.addRow("Warning at", self.cpu_warning_spin)
        cpu_form.addRow("Critical at", self.cpu_critical_spin)
        layout.addWidget(cpu_box)

        ram_box = QGroupBox("RAM Utilization (allocated / physical)")
        ram_form = QFormLayout(ram_box)
        self.ram_warning_spin = _ratio_spin(80.0, " %")
        self.ram_critical_spin = _ratio_spin(100.0, " %")
        ram_form.addRow("Warning at", self.ram_warning_spin)
        ram_form.addRow("Critical at", self.ram_critical_spin)
        layout.addWidget(ram_box)

        storage_box = QGroupBox("Storage Utilization (allocated / usable)")
        storage_form = QFormLayout(storage_box)
        self.storage_warning_spin = _ratio_spin(80.0, " %")
        self.storage_critical_spin = _ratio_spin(95.0, " %")
        storage_form.addRow("Warning at", self.storage_warning_spin)
        storage_form.addRow("Critical at", self.storage_critical_spin)
        layout.addWidget(storage_box)

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply)
        layout.addWidget(apply_button)

        layout.addStretch()

    def _selected_preset(self):
        key = self.preset_combo.currentData()
        return next((p for p in PRESETS if p.key == key), PRESETS[0])

    def _update_preset_description(self):
        self.preset_description_label.setText(self._selected_preset().description)
        self.preset_status_label.setText("")

    def _use_preset(self):
        t = self._selected_preset().thresholds
        self.cpu_warning_spin.setValue(t.cpu_warning_ratio)
        self.cpu_critical_spin.setValue(t.cpu_critical_ratio)
        self.ram_warning_spin.setValue(t.ram_warning_ratio * 100)
        self.ram_critical_spin.setValue(t.ram_critical_ratio * 100)
        self.storage_warning_spin.setValue(t.storage_warning_ratio * 100)
        self.storage_critical_spin.setValue(t.storage_critical_ratio * 100)
        self.preset_status_label.setText(
            f"\u2713 {self._selected_preset().label} values loaded below - click Apply to save."
        )

    def _load_from_service(self):
        self.primary_deployment_combo.blockSignals(True)
        self.primary_deployment_combo.setCurrentText(self.service.project.primary_deployment_model)
        self.primary_deployment_combo.blockSignals(False)

        self.dr_deployment_combo.blockSignals(True)
        self.dr_deployment_combo.setCurrentText(self.service.project.dr_deployment_model)
        self.dr_deployment_combo.blockSignals(False)

        self.primary_rack_capacity_spin.blockSignals(True)
        self.primary_rack_capacity_spin.setValue(self.service.project.primary_rack_capacity_u)
        self.primary_rack_capacity_spin.blockSignals(False)

        self.dr_rack_capacity_spin.blockSignals(True)
        self.dr_rack_capacity_spin.setValue(self.service.project.dr_rack_capacity_u)
        self.dr_rack_capacity_spin.blockSignals(False)

        t = self.service.thresholds
        self.cpu_warning_spin.setValue(t.cpu_warning_ratio)
        self.cpu_critical_spin.setValue(t.cpu_critical_ratio)
        self.ram_warning_spin.setValue(t.ram_warning_ratio * 100)
        self.ram_critical_spin.setValue(t.ram_critical_ratio * 100)
        self.storage_warning_spin.setValue(t.storage_warning_ratio * 100)
        self.storage_critical_spin.setValue(t.storage_critical_ratio * 100)

    def _apply(self):
        t = self.service.thresholds
        t.cpu_warning_ratio = self.cpu_warning_spin.value()
        t.cpu_critical_ratio = self.cpu_critical_spin.value()
        t.ram_warning_ratio = self.ram_warning_spin.value() / 100
        t.ram_critical_ratio = self.ram_critical_spin.value() / 100
        t.storage_warning_ratio = self.storage_warning_spin.value() / 100
        t.storage_critical_ratio = self.storage_critical_spin.value() / 100

        self.service.touch()
        self.preset_status_label.setText("\u2713 Applied - thresholds saved.")
