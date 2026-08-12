from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.calculations.thresholds import PRESETS
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
    """Warning thresholds for oversubscription calculations. Applied
    immediately on the Summary/VMs pages after clicking 'Apply'."""

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
