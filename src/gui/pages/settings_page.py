from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
    """Pragovi upozorenja za oversubscription izračune. Primjenjuju se odmah
    na Summary/Dashboard/VMs stranicama nakon klika na 'Apply'."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service

        self._create_ui()
        self._load_from_service()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Pragovi upozorenja koriste se za bojanje statusa (OK / Warning / "
            "Critical) na Summary i VMs stranicama."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

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
