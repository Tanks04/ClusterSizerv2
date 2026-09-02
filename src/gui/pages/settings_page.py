from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.calculations.thresholds import PRESETS
from src.models.workload_tier import WORKLOAD_TIER_NAMES, WORKLOAD_TIERS
from src.models.cluster_project import DEPLOYMENT_MODELS, PRIMARY
from src.services.project_service import ProjectService


class _NoWheelWhenUnfocused(QObject):
    """Blocks mouse-wheel scroll on a combo/spin box unless it already
    has keyboard focus - installed on every input in this scrollable
    page. Without this, Qt lets a combo/spin box under the cursor
    consume a wheel scroll and change ITS value instead of scrolling
    the page underneath it - exactly how someone scrolling past a
    Deployment Model dropdown or a threshold spinbox can accidentally
    change it without ever clicking on it. Click/tab into a field
    first (giving it focus) to intentionally scroll its value."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and not watched.hasFocus():
            event.ignore()
            return True
        return False


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
        self._no_wheel = _NoWheelWhenUnfocused(self)

        self._create_ui()
        self._load_from_service()

    def _create_ui(self):
        # The page can grow taller than the window once a project has a
        # few extra sites (each site adds a row to Deployment Model AND
        # Rack Capacity) - without this, content past the bottom is
        # unreachable, and worse, word-wrapped note labels can end up
        # squeezed into too little vertical space and render cut off/
        # overlapping instead of just being clipped. Same fix already
        # applied to SummaryPage and the entity dialogs.
        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

        info = QLabel(
            "Warning thresholds are used to color the status (OK / Warning / "
            "Critical) on the Summary and VMs pages."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        #
        # Sites - add/remove beyond the default Primary/DR pair. Primary
        # can never be removed (see ProjectService.remove_site) - too
        # much of the rest of the app assumes it always exists.
        #

        sites_box = QGroupBox("Sites")
        sites_layout = QVBoxLayout(sites_box)

        sites_note = QLabel(
            "Primary and DR always exist by default - add more if you have "
            "additional sites (a second DR, a cloud site, etc.). Primary "
            "can't be removed. A site still referenced by any Server/"
            "Storage/VM/Switch/Backup Destination/VLAN/Failover Assignment "
            "can't be removed either - reassign or delete those first."
        )
        sites_note.setWordWrap(True)
        sites_note.setStyleSheet("color: #757575; font-style: italic;")
        sites_layout.addWidget(sites_note)

        add_site_row = QHBoxLayout()
        self.new_site_edit = QLineEdit()
        self.new_site_edit.setPlaceholderText("e.g. DR2, Cloud Site...")
        add_site_row.addWidget(self.new_site_edit)
        add_site_button = QPushButton("Add Site")
        add_site_button.clicked.connect(self._add_site)
        add_site_row.addWidget(add_site_button)
        sites_layout.addLayout(add_site_row)

        self.sites_list_layout = QHBoxLayout()
        self.sites_list_layout.addWidget(QLabel("Current sites:"))
        sites_layout.addLayout(self.sites_list_layout)


        #
        # Deployment model (per-site - hybrid setups like on-prem
        # Primary + cloud DR/DRaaS are common). Rebuilt dynamically
        # whenever the site list changes - not a fixed Primary/DR pair.
        #

        self.deployment_box = QGroupBox("Deployment Model")
        self.deployment_form = QFormLayout(self.deployment_box)
        self.deployment_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        deployment_note = QLabel(
            "Set per site - a hybrid setup (e.g. on-premise Primary with a "
            "cloud DR/DRaaS) is common. Currently affects Rack Sizing on "
            "the Summary page and in the Word report - a Cloud site shows "
            "\"Cloud\" instead of trying to sum rack units/power, since "
            "that's not a concept that applies there. Applied immediately."
        )
        deployment_note.setWordWrap(True)
        deployment_note.setStyleSheet("color: #757575; font-style: italic;")
        self.deployment_form.addRow(deployment_note)


        #
        # Rack Capacity (per site) - how many U are AVAILABLE, separate
        # from Rack Sizing's "how many U are USED by entered equipment"
        #

        self.rack_capacity_box = QGroupBox("Rack Capacity")
        self.rack_capacity_form = QFormLayout(self.rack_capacity_box)
        self.rack_capacity_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

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
        self.rack_capacity_form.addRow(rack_capacity_note)


        self.site_names_shown: list[str] = []
        self.deployment_combos: dict[str, QComboBox] = {}
        self.rack_capacity_spins: dict[str, QSpinBox] = {}

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
        self.preset_combo.installEventFilter(self._no_wheel)
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


        #
        # Manual thresholds
        #

        cpu_box = QGroupBox("CPU Oversubscription (vCPU : physical core)")
        cpu_form = QFormLayout(cpu_box)
        cpu_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.cpu_warning_spin = _ratio_spin(4.0, " : 1")
        self.cpu_critical_spin = _ratio_spin(6.0, " : 1")
        self.cpu_warning_spin.installEventFilter(self._no_wheel)
        self.cpu_critical_spin.installEventFilter(self._no_wheel)
        cpu_form.addRow("Warning at", self.cpu_warning_spin)
        cpu_form.addRow("Critical at", self.cpu_critical_spin)

        ram_box = QGroupBox("RAM Utilization (allocated / physical)")
        ram_form = QFormLayout(ram_box)
        ram_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.ram_warning_spin = _ratio_spin(80.0, " %")
        self.ram_critical_spin = _ratio_spin(100.0, " %")
        self.ram_warning_spin.installEventFilter(self._no_wheel)
        self.ram_critical_spin.installEventFilter(self._no_wheel)
        ram_form.addRow("Warning at", self.ram_warning_spin)
        ram_form.addRow("Critical at", self.ram_critical_spin)

        storage_box = QGroupBox("Storage Utilization (allocated / usable)")
        storage_form = QFormLayout(storage_box)
        storage_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.storage_warning_spin = _ratio_spin(80.0, " %")
        self.storage_critical_spin = _ratio_spin(95.0, " %")
        self.storage_warning_spin.installEventFilter(self._no_wheel)
        self.storage_critical_spin.installEventFilter(self._no_wheel)
        storage_form.addRow("Warning at", self.storage_warning_spin)
        storage_form.addRow("Critical at", self.storage_critical_spin)

        self.tiers_box = QGroupBox("Workload Tiers (vCPU : physical core tolerance)")
        tiers_form = QFormLayout(self.tiers_box)
        tiers_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        tiers_note = QLabel(
            "Used by the tier-weighted Effective CPU check (Summary/Attention) "
            "and Cluster Preparation sizing. Starts from commonly-cited "
            "defaults - override any of them for this project if your own "
            "experience says otherwise."
        )
        tiers_note.setWordWrap(True)
        tiers_note.setStyleSheet("color: #757575; font-style: italic;")
        tiers_form.addRow(tiers_note)

        self.tier_ratio_spins: dict[str, QDoubleSpinBox] = {}
        for tier_name in WORKLOAD_TIER_NAMES:
            spin = _ratio_spin(WORKLOAD_TIERS[tier_name].default_ratio)
            spin.setRange(1.0, 100.0)
            spin.installEventFilter(self._no_wheel)
            self.tier_ratio_spins[tier_name] = spin
            tiers_form.addRow(tier_name, spin)

        row1 = QHBoxLayout()
        row1.addWidget(sites_box, 1)
        row1.addWidget(self.deployment_box, 1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(self.rack_capacity_box, 1)
        row2.addWidget(preset_box, 1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(cpu_box, 1)
        row3.addWidget(ram_box, 1)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(storage_box, 1)
        row4.addWidget(self.tiers_box, 1)
        layout.addLayout(row4)

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply)
        layout.addWidget(apply_button)

        layout.addStretch()
        self._update_preset_description()

    def _add_site(self):
        name = self.new_site_edit.text().strip()
        if not name:
            return
        if name in self.service.project.site_names:
            QMessageBox.information(self, "Add Site", f'"{name}" already exists.')
            return
        self.service.add_site(name)
        self.new_site_edit.clear()
        self._rebuild_site_rows()

    def _remove_site(self, name: str):
        confirm = QMessageBox.question(
            self, "Remove Site", f'Remove "{name}"? You can undo with Ctrl+Z.',
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.remove_site(name)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Cannot Remove Site", str(exc))
            return
        self._rebuild_site_rows()

    def _rebuild_site_rows(self):
        """Rebuilt whenever the site list itself changes (add/remove) -
        not on every load, since QFormLayout has no cheap way to just
        update existing rows' labels in place when the underlying site
        set changes shape."""
        site_names = self.service.project.site_names
        if site_names == self.site_names_shown:
            self._load_site_values()
            return

        while self.deployment_form.rowCount() > 1:  # keep row 0 (the note)
            self.deployment_form.removeRow(1)
        while self.rack_capacity_form.rowCount() > 1:
            self.rack_capacity_form.removeRow(1)
        self.deployment_combos.clear()
        self.rack_capacity_spins.clear()

        # Clear the "Current sites" chip row, keeping only its leading
        # "Current sites:" label (index 0).
        while self.sites_list_layout.count() > 1:
            item = self.sites_list_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for site in site_names:
            combo = QComboBox()
            combo.addItems(DEPLOYMENT_MODELS)
            combo.currentTextChanged.connect(
                lambda text, s=site: self.service.set_deployment_model(s, text)
            )
            combo.installEventFilter(self._no_wheel)
            self.deployment_combos[site] = combo
            self.deployment_form.addRow(self._site_row_label(site), combo)

            spin = QSpinBox()
            spin.setRange(0, 1000)
            spin.setSuffix(" U")
            spin.setSpecialValueText("(not set)")
            spin.installEventFilter(self._no_wheel)
            spin.valueChanged.connect(
                lambda value, s=site: self.service.set_rack_capacity_u(s, value)
            )
            self.rack_capacity_spins[site] = spin
            self.rack_capacity_form.addRow(self._site_row_label(site), spin)

            self.sites_list_layout.addWidget(self._site_chip(site))

        self.sites_list_layout.addStretch()
        self.site_names_shown = list(site_names)
        self._load_site_values()

    def _site_chip(self, site: str) -> QWidget:
        """Site name + inline Remove button for the "Current sites" row
        right in the Sites box - so add and remove live in the same
        place, instead of remove being buried in the Deployment Model
        or Rack Capacity sections further down."""
        chip = QWidget()
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(4, 2, 4, 2)
        chip_layout.setSpacing(4)
        chip.setStyleSheet("background-color: #e0e0e0; border-radius: 4px;")
        chip_layout.addWidget(QLabel(site))
        if site != PRIMARY:
            remove_button = QPushButton("\u2715")
            remove_button.setFixedWidth(20)
            remove_button.setToolTip(f'Remove "{site}"')
            remove_button.clicked.connect(lambda: self._remove_site(site))
            chip_layout.addWidget(remove_button)
        return chip

    def _site_row_label(self, site: str) -> QWidget:
        """Site name + a Remove button for anything but Primary, so
        removing a site doesn't require leaving this page."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(site))
        if site != PRIMARY:
            remove_button = QPushButton("\u2715")
            remove_button.setFixedWidth(24)
            remove_button.setToolTip(f'Remove "{site}"')
            remove_button.clicked.connect(lambda: self._remove_site(site))
            row_layout.addWidget(remove_button)
        row_layout.addStretch()
        return row

    def _load_site_values(self):
        for site, combo in self.deployment_combos.items():
            combo.blockSignals(True)
            combo.setCurrentText(self.service.project.deployment_model_for(site))
            combo.blockSignals(False)
        for site, spin in self.rack_capacity_spins.items():
            spin.blockSignals(True)
            spin.setValue(self.service.project.rack_capacity_u_for(site))
            spin.blockSignals(False)

    def _selected_preset(self):
        key = self.preset_combo.currentData()
        return next((p for p in PRESETS if p.key == key), PRESETS[0])

    def _update_preset_description(self):
        preset = self._selected_preset()
        self.preset_description_label.setText(preset.description)
        # Show the values immediately on selection, not only after
        # clicking "Use This Preset" - that button now just confirms
        # the already-shown selection (see its own status message).
        t = preset.thresholds
        self.cpu_warning_spin.setValue(t.cpu_warning_ratio)
        self.cpu_critical_spin.setValue(t.cpu_critical_ratio)
        self.ram_warning_spin.setValue(t.ram_warning_ratio * 100)
        self.ram_critical_spin.setValue(t.ram_critical_ratio * 100)
        self.storage_warning_spin.setValue(t.storage_warning_ratio * 100)
        self.storage_critical_spin.setValue(t.storage_critical_ratio * 100)
        self.preset_status_label.setText("")

    def _use_preset(self):
        self.preset_status_label.setText(
            f"\u2713 {self._selected_preset().label} values loaded below - click Apply to save."
        )

    def _load_from_service(self):
        self._rebuild_site_rows()

        t = self.service.thresholds
        self.cpu_warning_spin.setValue(t.cpu_warning_ratio)
        self.cpu_critical_spin.setValue(t.cpu_critical_ratio)
        self.ram_warning_spin.setValue(t.ram_warning_ratio * 100)
        self.ram_critical_spin.setValue(t.ram_critical_ratio * 100)
        self.storage_warning_spin.setValue(t.storage_warning_ratio * 100)
        self.storage_critical_spin.setValue(t.storage_critical_ratio * 100)

        overrides = self.service.project.tier_ratio_overrides
        for tier_name, spin in self.tier_ratio_spins.items():
            spin.setValue(overrides.get(tier_name, WORKLOAD_TIERS[tier_name].default_ratio))

    def _apply(self):
        t = self.service.thresholds
        t.cpu_warning_ratio = self.cpu_warning_spin.value()
        t.cpu_critical_ratio = self.cpu_critical_spin.value()
        t.ram_warning_ratio = self.ram_warning_spin.value() / 100
        t.ram_critical_ratio = self.ram_critical_spin.value() / 100
        t.storage_warning_ratio = self.storage_warning_spin.value() / 100
        t.storage_critical_ratio = self.storage_critical_spin.value() / 100

        overrides = self.service.project.tier_ratio_overrides
        for tier_name, spin in self.tier_ratio_spins.items():
            catalog_default = WORKLOAD_TIERS[tier_name].default_ratio
            if abs(spin.value() - catalog_default) > 0.001:
                overrides[tier_name] = spin.value()
            else:
                overrides.pop(tier_name, None)

        self.service.touch()
        self.preset_status_label.setText("\u2713 Applied - thresholds saved.")
