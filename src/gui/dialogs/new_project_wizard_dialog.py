from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.calculations.thresholds import PRESETS


class NewProjectWizardDialog(QDialog):
    """Optional alternative to plain File > New - a few quick questions
    (sites, hypervisor, a rough VM count) that set up sensible starting
    defaults, instead of an empty project where the person has to
    discover Settings/Servers/VMs all separately. Every answer here is
    something the person could set up manually afterward anyway - this
    just saves the first few clicks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project Wizard")
        self.setFixedSize(420, 320)

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_sites_page())
        self.stack.addWidget(self._build_hypervisor_page())
        self.stack.addWidget(self._build_servers_page())
        self.stack.addWidget(self._build_vms_page())
        layout.addWidget(self.stack)

        self.step_label = QLabel()
        layout.addWidget(self.step_label)

        nav_row = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._go_back)
        nav_row.addWidget(self.back_button)
        nav_row.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        nav_row.addWidget(cancel_button)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_button)
        layout.addLayout(nav_row)

        self._update_nav()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            parent_geo = parent.frameGeometry()
            x = parent_geo.center().x() - self.width() // 2
            y = parent_geo.center().y() - self.height() // 2
            self.move(max(0, x), max(0, y))

    # ------------------------------------------------------------------
    # Page 1 - Sites
    # ------------------------------------------------------------------

    def _build_sites_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(QLabel("<b>How many sites?</b>"))
        page_layout.addWidget(QLabel(
            "You can always add or remove sites later from Settings - this "
            "just saves the first step."
        ))

        self.sites_group = QButtonGroup(self)
        self.sites_primary_only = QRadioButton("Primary only")
        self.sites_primary_dr = QRadioButton("Primary + DR")
        self.sites_primary_dr.setChecked(True)
        self.sites_primary_dr_more = QRadioButton("Primary + DR + more")
        for button in (self.sites_primary_only, self.sites_primary_dr, self.sites_primary_dr_more):
            self.sites_group.addButton(button)
            page_layout.addWidget(button)

        more_row = QHBoxLayout()
        more_row.addWidget(QLabel("    Additional DR sites (DR2, DR3, ...):"))
        self.extra_sites_spin = QSpinBox()
        self.extra_sites_spin.setRange(1, 10)
        self.extra_sites_spin.setValue(1)
        more_row.addWidget(self.extra_sites_spin)
        more_row.addStretch()
        page_layout.addLayout(more_row)

        page_layout.addStretch()
        return page

    def get_site_names(self) -> list[str]:
        if self.sites_primary_only.isChecked():
            return ["Primary"]
        if self.sites_primary_dr_more.isChecked():
            extra_count = self.extra_sites_spin.value()
            return ["Primary", "DR"] + [f"DR{i + 2}" for i in range(extra_count)]
        return ["Primary", "DR"]

    # ------------------------------------------------------------------
    # Page 2 - Hypervisor
    # ------------------------------------------------------------------

    def _build_hypervisor_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(QLabel("<b>Which hypervisor?</b>"))
        page_layout.addWidget(QLabel(
            "Pre-fills the CPU/RAM/Storage warning thresholds from a sensible "
            "starting preset for this hypervisor - same as \"Use This Preset\" "
            "on the Settings tab. You can change any of these later."
        ))

        form = QFormLayout()
        self.hypervisor_combo = QComboBox()
        self.hypervisor_combo.addItem("Skip (use default thresholds)", userData=None)
        for preset in PRESETS:
            self.hypervisor_combo.addItem(preset.label, userData=preset.key)
        form.addRow("Hypervisor", self.hypervisor_combo)
        page_layout.addLayout(form)

        page_layout.addStretch()
        return page

    def get_hypervisor_preset_key(self) -> str | None:
        return self.hypervisor_combo.currentData()

    # ------------------------------------------------------------------
    # Page 3 - Servers
    # ------------------------------------------------------------------

    def _build_servers_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(QLabel("<b>Servers (optional)</b>"))
        page_layout.addWidget(QLabel(
            "If you already know roughly what hardware you're sizing, we'll "
            "create that many identical servers - adjust each one afterward. "
            "Leave server count at 0 to skip this and add servers yourself later."
        ))

        form = QFormLayout()
        self.server_count_spin = QSpinBox()
        self.server_count_spin.setRange(0, 200)
        self.server_count_spin.setSuffix(" servers")
        self.server_count_spin.valueChanged.connect(self._update_server_specs_enabled)
        form.addRow("Server count", self.server_count_spin)

        self.server_sockets_spin = QSpinBox()
        self.server_sockets_spin.setRange(1, 16)
        self.server_sockets_spin.setValue(2)
        form.addRow("Sockets", self.server_sockets_spin)

        self.server_cores_spin = QSpinBox()
        self.server_cores_spin.setRange(1, 256)
        self.server_cores_spin.setValue(16)
        form.addRow("Cores per socket", self.server_cores_spin)

        self.server_ram_spin = QSpinBox()
        self.server_ram_spin.setRange(1, 100000)
        self.server_ram_spin.setValue(256)
        self.server_ram_spin.setSuffix(" GB")
        form.addRow("RAM per server", self.server_ram_spin)

        page_layout.addLayout(form)
        page_layout.addStretch()
        self._update_server_specs_enabled()
        return page

    def _update_server_specs_enabled(self) -> None:
        enabled = self.server_count_spin.value() > 0
        self.server_sockets_spin.setEnabled(enabled)
        self.server_cores_spin.setEnabled(enabled)
        self.server_ram_spin.setEnabled(enabled)

    def get_server_generation_params(self) -> tuple[int, int, int, int] | None:
        """Returns (count, sockets, cores_per_socket, ram_gb), or None
        if server count is 0 (skipped)."""
        count = self.server_count_spin.value()
        if count <= 0:
            return None
        return (count, self.server_sockets_spin.value(), self.server_cores_spin.value(), self.server_ram_spin.value())

    # ------------------------------------------------------------------
    # Page 4 - VMs
    # ------------------------------------------------------------------

    def _build_vms_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(QLabel("<b>Rough VM count (optional)</b>"))
        page_layout.addWidget(QLabel(
            "If you already know roughly how many VMs and how much total vCPU/"
            "RAM/Disk you need, we'll create that many VMs, splitting the "
            "totals evenly across them - rename and adjust each one "
            "afterward. Leave VM count at 0 to skip this and add VMs "
            "yourself later."
        ))

        form = QFormLayout()
        self.vm_count_spin = QSpinBox()
        self.vm_count_spin.setRange(0, 500)
        self.vm_count_spin.setSuffix(" VMs")
        self.vm_count_spin.valueChanged.connect(self._update_vm_totals_enabled)
        form.addRow("VM count", self.vm_count_spin)

        self.total_vcpu_spin = QSpinBox()
        self.total_vcpu_spin.setRange(0, 100000)
        self.total_vcpu_spin.setSuffix(" vCPU total")
        form.addRow("Total vCPU", self.total_vcpu_spin)

        self.total_ram_spin = QDoubleSpinBox()
        self.total_ram_spin.setRange(0, 1_000_000)
        self.total_ram_spin.setSuffix(" GB total")
        self.total_ram_spin.setDecimals(0)
        form.addRow("Total RAM", self.total_ram_spin)

        self.total_disk_spin = QDoubleSpinBox()
        self.total_disk_spin.setRange(0, 10_000_000)
        self.total_disk_spin.setSuffix(" GB total")
        self.total_disk_spin.setDecimals(0)
        form.addRow("Total Disk", self.total_disk_spin)

        page_layout.addLayout(form)
        page_layout.addStretch()
        self._update_vm_totals_enabled()
        return page

    def _update_vm_totals_enabled(self) -> None:
        enabled = self.vm_count_spin.value() > 0
        self.total_vcpu_spin.setEnabled(enabled)
        self.total_ram_spin.setEnabled(enabled)
        self.total_disk_spin.setEnabled(enabled)

    def get_vm_generation_params(self) -> tuple[int, int, float, float] | None:
        """Returns (count, total_vcpu, total_ram_gb, total_disk_gb), or
        None if VM count is 0 (skipped)."""
        count = self.vm_count_spin.value()
        if count <= 0:
            return None
        return (count, self.total_vcpu_spin.value(), self.total_ram_spin.value(), self.total_disk_spin.value())

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_next(self) -> None:
        if self.stack.currentIndex() == self.stack.count() - 1:
            self.accept()
            return
        self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self._update_nav()

    def _go_back(self) -> None:
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._update_nav()

    def _update_nav(self) -> None:
        index = self.stack.currentIndex()
        total = self.stack.count()
        self.step_label.setText(f"Step {index + 1} of {total}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Finish" if index == total - 1 else "Next")
