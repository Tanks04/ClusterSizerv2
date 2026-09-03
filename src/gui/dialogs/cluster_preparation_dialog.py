from PySide6.QtWidgets import (
    QCheckBox,
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
    QWizard,
    QWizardPage,
)

from src.calculations.cluster_preparation import (
    compute_sizing, SizingPolicy, HostSpec, HA_LEVELS, ManualDemand,
    compute_site_recommendation as compute_site_recommendation_calc,
)
from src.calculations.thresholds import PRESETS
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.backup_destination import BackupDestination, DESTINATION_TYPES
from src.models.failover_assignment import FailoverAssignment
from src.models.workload_tier import WORKLOAD_TIER_NAMES, WORKLOAD_TIERS, DEFAULT_WORKLOAD_TIER
from src.models.virtual_machine import DR_CATEGORIES
from src.gui.error_handling import report_error

_HA_EXPLANATIONS = {
    "None": "Fewest hosts possible for today's demand, no reserved headroom. HA is not configured at all - a host failure means its VMs stay down until manually recovered.",
    "Basic HA": "Same host count as None (still the fewest possible) - but HA IS enabled, so VMs restart automatically elsewhere on a host failure. No capacity is reserved for that though, so survivors take the full load in a heavy overload until you add capacity back.",
    "N+1": "One extra host reserved on top of what your VMs need - losing any single host leaves NO capacity shortfall, survivors stay within your target oversubscription ratio instead of overloading.",
    "N+2": "Two extra hosts reserved - survive losing two hosts at once (e.g. one down for maintenance, one fails unexpectedly) with no capacity shortfall.",
}


# ----------------------------------------------------------------------
# Page 1 - Hypervisor
# ----------------------------------------------------------------------

class HypervisorPage(QWizardPage):
    """Which platform you're sizing for - reuses the same vendor presets
    already on the Settings tab (Thresholds.PRESETS), so the "commonly
    cited" ratio referenced here is the exact same one, not a second
    guess at the same numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Hypervisor")
        self.setSubTitle("Which platform are you sizing for? Used to derive a sensible target oversubscription ratio.")

        layout = QFormLayout(self)

        self.vendor_combo = QComboBox()
        for preset in PRESETS:
            self.vendor_combo.addItem(preset.label, preset.key)
        self.vendor_combo.currentIndexChanged.connect(self._update_info)
        layout.addRow("Hypervisor", self.vendor_combo)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #757575; font-style: italic;")
        layout.addRow(self.info_label)

        self._update_info()

    def _update_info(self):
        preset = PRESETS[self.vendor_combo.currentIndex()]
        target = preset.thresholds.cpu_warning_ratio * 0.75
        self.info_label.setText(
            f"{preset.description} The Result page will optimize toward roughly "
            f"{target:.2f}:1 vCPU:pCPU (about 3/4 of the {preset.thresholds.cpu_warning_ratio:.0f}:1 "
            "warning threshold, comfortably below it)."
        )

    def selected_preset(self):
        return PRESETS[self.vendor_combo.currentIndex()]


# ----------------------------------------------------------------------
# Page 2 - Workload
# ----------------------------------------------------------------------

class WorkloadPage(QWizardPage):
    """Shows the workload mix already set per-VM on the VMs tab - you
    don't configure oversubscription ratios here, they come from each
    VM's Workload Tier (set on the VMs tab, including the "Bulk edit"
    row there for setting it on every VM at once). The catalog defaults
    (src/models/workload_tier.py - commonly-cited safe vCPU:pCPU ranges
    per SLA tier) are used as-is unless you explicitly opt into
    fine-tuning them below."""

    def __init__(self, project: ClusterProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.setTitle("Workload")
        self.setSubTitle("Based on the Workload Tier already set per VM on the VMs tab.")

        layout = QVBoxLayout(self)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.ratio_spins: dict[str, QDoubleSpinBox] = {}

        self.ratio_box = QGroupBox("Fine-tune oversubscription ratios (optional)")
        self.ratio_box.setCheckable(True)
        self.ratio_box.setChecked(False)
        self.ratio_box.setToolTip(
            "Off by default - the per-tier defaults below are used as-is. "
            "Check this only if you have your own guidance and want to override them."
        )
        ratio_form = QFormLayout(self.ratio_box)

        for name in WORKLOAD_TIER_NAMES:
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 50.0)
            spin.setSuffix(" : 1")
            spin.setValue(WORKLOAD_TIERS[name].default_ratio)
            ratio_form.addRow(name, spin)
            self.ratio_spins[name] = spin

        layout.addWidget(self.ratio_box)

        self.manual_demand_box = QGroupBox("No VMs yet - enter aggregate demand directly")
        self.manual_demand_box.setToolTip(
            "Sizes from these totals for a brand-new environment before VMs "
            "exist. Ignored once real VMs are added."
        )
        manual_form = QFormLayout(self.manual_demand_box)

        self.manual_vcpu_spin = QSpinBox()
        self.manual_vcpu_spin.setRange(0, 100000)
        self.manual_vcpu_spin.setSuffix(" vCPU")
        manual_form.addRow("Total vCPU needed", self.manual_vcpu_spin)

        self.manual_ram_spin = QDoubleSpinBox()
        self.manual_ram_spin.setRange(0.0, 1000000.0)
        self.manual_ram_spin.setSuffix(" GB")
        manual_form.addRow("Total RAM needed", self.manual_ram_spin)

        self.manual_disk_spin = QDoubleSpinBox()
        self.manual_disk_spin.setRange(0.0, 10000000.0)
        self.manual_disk_spin.setSuffix(" GB")
        manual_form.addRow("Total Disk needed", self.manual_disk_spin)

        self.manual_tier_combo = QComboBox()
        self.manual_tier_combo.addItems(WORKLOAD_TIER_NAMES)
        self.manual_tier_combo.setCurrentText(DEFAULT_WORKLOAD_TIER)
        manual_form.addRow("Workload Tier (applies to the whole total)", self.manual_tier_combo)

        layout.addWidget(self.manual_demand_box)
        layout.addStretch()

    def manual_demand(self) -> "ManualDemand":
        return ManualDemand(
            vcpu=self.manual_vcpu_spin.value(),
            ram_gb=self.manual_ram_spin.value(),
            disk_gb=self.manual_disk_spin.value(),
            workload_tier=self.manual_tier_combo.currentText(),
        )

    def initializePage(self):
        primary_vms = self.project.vms_at("Primary")
        dr_site_count = len(self.project.vms_at("DR"))

        if not primary_vms:
            msg = "No VMs on the VMs tab yet - enter aggregate demand below, or add real VMs there first."
            if dr_site_count:
                msg += f" ({dr_site_count} VM(s) are tagged site=DR and would be excluded from this sizing anyway.)"
            self.summary_label.setText(msg)
            self.manual_demand_box.setVisible(True)
            return

        self.manual_demand_box.setVisible(False)

        breakdown: dict[str, int] = {}
        for vm in primary_vms:
            breakdown[vm.workload_tier] = breakdown.get(vm.workload_tier, 0) + 1
        breakdown_text = ", ".join(f"{count} {name}" for name, count in sorted(breakdown.items()))

        dr_note = ""
        if dr_site_count:
            dr_note = (
                f"\n\n({dr_site_count} more VM(s) are already tagged site=DR and are "
                "NOT included in this count - they already live on DR, not Primary.)"
            )

        self.summary_label.setText(
            f"{len(primary_vms)} Primary VMs: {breakdown_text}.{dr_note}\n\n"
            "Each tier's default oversubscription ratio:\n" +
            "\n".join(
                f"  \u2022 {name}: {WORKLOAD_TIERS[name].default_ratio:.0f}:1 "
                f"(commonly cited: {WORKLOAD_TIERS[name].ratio_min:.0f}:1-"
                f"{WORKLOAD_TIERS[name].ratio_max:.0f}:1)"
                for name in WORKLOAD_TIER_NAMES
            )
        )

    def ratio_overrides(self) -> dict[str, float]:
        if not self.ratio_box.isChecked():
            return {}
        return {name: spin.value() for name, spin in self.ratio_spins.items()}


# ----------------------------------------------------------------------
# Page 3 - Policy
# ----------------------------------------------------------------------

class PolicyPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Policy")
        self.setSubTitle(
            "If you skip these, sensible defaults are used - N+1, 30% growth, "
            "20% reserve, 2 cores/host reserved for the hypervisor, Hyperthreading off."
        )

        layout = QFormLayout(self)

        self.ha_combo = QComboBox()
        self.ha_combo.addItems(HA_LEVELS)
        self.ha_combo.setCurrentText("N+1")
        self.ha_combo.currentTextChanged.connect(self._update_ha_explanation)
        layout.addRow("High Availability", self.ha_combo)

        self.ha_explanation_label = QLabel("")
        self.ha_explanation_label.setWordWrap(True)
        self.ha_explanation_label.setStyleSheet("color: #757575; font-style: italic;")
        layout.addRow("", self.ha_explanation_label)
        self._update_ha_explanation()

        self.growth_spin = QDoubleSpinBox()
        self.growth_spin.setRange(0.0, 500.0)
        self.growth_spin.setSuffix(" %")
        self.growth_spin.setValue(30.0)
        self.growth_spin.setToolTip(
            "Applied equally to vCPU, RAM, and storage demand - a margin for "
            "adding VMs later, not a growth prediction."
        )
        layout.addRow("Expected Growth\n(vCPU + RAM + Storage)", self.growth_spin)

        self.reserve_spin = QDoubleSpinBox()
        self.reserve_spin.setRange(0.0, 90.0)
        self.reserve_spin.setSuffix(" %")
        self.reserve_spin.setValue(20.0)
        self.reserve_spin.setToolTip(
            "RAM held back for hypervisor/management/overhead - not available to VMs."
        )
        layout.addRow("Memory Reserve", self.reserve_spin)

        self.storage_overhead_spin = QDoubleSpinBox()
        self.storage_overhead_spin.setRange(0.0, 90.0)
        self.storage_overhead_spin.setSuffix(" %")
        self.storage_overhead_spin.setValue(20.0)
        self.storage_overhead_spin.setToolTip(
            "RAID/erasure-coding overhead plus headroom, going from raw to "
            "usable storage capacity - same idea as the Storage tab's own field."
        )
        layout.addRow("Storage Overhead", self.storage_overhead_spin)

        self.cpu_reserve_spin = QSpinBox()
        self.cpu_reserve_spin.setRange(0, 16)
        self.cpu_reserve_spin.setSuffix(" cores/host")
        self.cpu_reserve_spin.setValue(2)
        self.cpu_reserve_spin.setToolTip(
            "Cores per host reserved for the hypervisor itself, before sizing. "
            "Set to 0 to size on raw capacity alone."
        )
        layout.addRow("Hypervisor CPU Reserve", self.cpu_reserve_spin)

        self.ht_check = QCheckBox("Hyperthreading Enabled")
        self.ht_check.setChecked(False)
        self.ht_check.setToolTip(
            "Off by default - HT gains vary by workload. Editable per-field on "
            "the Result page afterward."
        )
        layout.addRow("", self.ht_check)

    def _update_ha_explanation(self):
        self.ha_explanation_label.setText(_HA_EXPLANATIONS.get(self.ha_combo.currentText(), ""))


# ----------------------------------------------------------------------
# Page 4 - Result (includes the optimized, editable host spec)
# ----------------------------------------------------------------------

class ResultPage(QWizardPage):
    def __init__(self, wizard: "ClusterPreparationWizard", parent=None):
        super().__init__(parent)
        self._wizard_ref = wizard
        self.setTitle("Result")
        self.setSubTitle(
            "The host spec below is OPTIMIZED for you - fewest hosts, landing close to "
            "the target ratio. Adjust it and the numbers recalculate live."
        )

        # The result text plus the editable spec box comfortably exceeds
        # a typical wizard page's fixed height - without this, content
        # past the bottom (notably the hypervisor-CPU-reservation warning
        # and, once queued, the "click Finish" confirmation) is simply
        # cut off with no way to reach it. Same fix already applied to
        # Summary/Settings for the same class of problem.
        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # --- Editable, optimized host spec ---
        spec_box = QGroupBox("Recommended Host Spec (editable)")
        spec_form = QFormLayout(spec_box)

        self._updating_spec_fields = False  # guards against feedback loops while pre-filling

        self.sockets_spin = QSpinBox()
        self.sockets_spin.setRange(1, 8)
        self.sockets_spin.valueChanged.connect(self._on_spec_edited)
        spec_form.addRow("Sockets", self.sockets_spin)

        self.cores_spin = QSpinBox()
        self.cores_spin.setRange(1, 256)
        self.cores_spin.valueChanged.connect(self._on_spec_edited)
        spec_form.addRow("Cores / Socket", self.cores_spin)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 4)
        self.threads_spin.valueChanged.connect(self._on_spec_edited)
        spec_form.addRow("Threads / Core", self.threads_spin)

        self.ht_check = QCheckBox("Hyperthreading Enabled")
        self.ht_check.toggled.connect(self._on_spec_edited)
        spec_form.addRow("", self.ht_check)

        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(16, 32768)
        self.ram_spin.setSuffix(" GB")
        self.ram_spin.valueChanged.connect(self._on_spec_edited)
        spec_form.addRow("RAM / Host", self.ram_spin)

        layout.addWidget(spec_box)

        refresh_button = QPushButton("\U0001f504 Reset to Optimized Suggestion")
        refresh_button.setToolTip("Discards your edits above and recomputes the optimized recommendation from scratch.")
        refresh_button.clicked.connect(self._reset_to_optimized)
        layout.addWidget(refresh_button)

        button_row = QHBoxLayout()
        self.add_primary_button = QPushButton("Add Recommended Cluster to Project (Primary)")
        self.add_primary_button.setToolTip("Adds the recommended servers AND storage together as one undoable action.")
        self.add_primary_button.clicked.connect(self._wizard_ref.add_primary_cluster)
        button_row.addWidget(self.add_primary_button)

        self.add_dr_button = QPushButton("Add Recommended Cluster to Project (DR)")
        self.add_dr_button.setToolTip("Adds the recommended servers AND storage together as one undoable action.")
        self.add_dr_button.clicked.connect(self._wizard_ref.add_dr_cluster)
        button_row.addWidget(self.add_dr_button)
        layout.addLayout(button_row)

        layout.addStretch()

    def initializePage(self):
        self._wizard_ref.host_spec_override = None  # start fresh each time this page is entered
        self._wizard_ref.recompute()

    def fill_spec_fields(self, spec: HostSpec):
        self._updating_spec_fields = True
        self.sockets_spin.setValue(spec.sockets)
        self.cores_spin.setValue(spec.cores_per_socket)
        self.threads_spin.setValue(spec.threads_per_core)
        self.ht_check.setChecked(spec.hyperthreading_enabled)
        self.ram_spin.setValue(int(spec.ram_gb))
        self._updating_spec_fields = False

    def current_spec_fields(self) -> HostSpec:
        return HostSpec(
            sockets=self.sockets_spin.value(),
            cores_per_socket=self.cores_spin.value(),
            threads_per_core=self.threads_spin.value(),
            hyperthreading_enabled=self.ht_check.isChecked(),
            ram_gb=float(self.ram_spin.value()),
        )

    def _on_spec_edited(self):
        if self._updating_spec_fields:
            return  # programmatic fill_spec_fields() call, not a real user edit
        self._wizard_ref.host_spec_override = self.current_spec_fields()
        self._wizard_ref.recompute(refill_spec_fields=False)

    def _reset_to_optimized(self):
        self._wizard_ref.host_spec_override = None
        self._wizard_ref.recompute()


# ----------------------------------------------------------------------
# Page 5 - Additional Sites (optional, one block per non-Primary site)
# ----------------------------------------------------------------------

class AdditionalSitesPage(QWizardPage):
    """One block per site in project.site_names other than Primary -
    opt in per site, pick which DR Categories should be sized for it,
    see a live recommendation, and add it - reusing Primary's host spec
    for consistent hardware across sites. Driven by DR Category
    selection rather than requiring FailoverAssignment records to
    already exist, matching how a real DR conversation actually goes
    ("everything except DWH and test/dev")."""

    def __init__(self, wizard: "ClusterPreparationWizard", parent=None):
        super().__init__(parent)
        self._wizard_ref = wizard
        self.setTitle("Additional Sites")
        self.setSubTitle(
            "Optional - recommend a cluster for other sites too, sized to hold only "
            "the DR Categories you select below. Reuses the same host spec as Primary."
        )

        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self._layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

        self.no_sites_label = QLabel(
            "No additional sites yet - add one on the Settings tab (Sites section) "
            "first if you want a recommendation for a DR/second site."
        )
        self.no_sites_label.setWordWrap(True)
        self.no_sites_label.setVisible(False)
        self._layout.addWidget(self.no_sites_label)

        self._site_widgets: dict[str, dict] = {}
        self._known_sites: list[str] = []
        self._layout.addStretch()

    def initializePage(self):
        current_sites = [s for s in self._wizard_ref.project.site_names if s != "Primary"]
        if current_sites == self._known_sites:
            self._recompute_all()
            return

        for widgets in self._site_widgets.values():
            widgets["box"].setParent(None)
            widgets["box"].deleteLater()
        self._site_widgets.clear()

        self.no_sites_label.setVisible(not current_sites)

        stretch_item = self._layout.takeAt(self._layout.count() - 1)  # remove trailing stretch
        for site in current_sites:
            box = self._build_site_box(site)
            self._layout.insertWidget(self._layout.count(), box)
        if stretch_item is not None:
            self._layout.addItem(stretch_item)
        else:
            self._layout.addStretch()

        self._known_sites = current_sites
        self._recompute_all()

    def _build_site_box(self, site: str) -> QGroupBox:
        box = QGroupBox(f"Recommend for {site}")
        box.setCheckable(True)
        box.setChecked(False)
        form = QVBoxLayout(box)

        category_checks = {}
        for category in DR_CATEGORIES:
            check = QCheckBox(category)
            check.setChecked(category in ("Core / Mission-Critical", "Important"))
            check.toggled.connect(lambda checked=False, s=site: self._recompute_site(s))
            form.addWidget(check)
            category_checks[category] = check

        result_label = QLabel("")
        result_label.setWordWrap(True)
        form.addWidget(result_label)

        add_button = QPushButton(f"Add Recommended Cluster to Project ({site})")
        add_button.clicked.connect(lambda checked=False, s=site: self._wizard_ref.add_site_cluster(s))
        form.addWidget(add_button)

        box.toggled.connect(lambda checked=False, s=site: self._recompute_site(s))

        self._site_widgets[site] = {
            "box": box,
            "category_checks": category_checks,
            "result_label": result_label,
            "add_button": add_button,
        }
        return box

    def selected_categories(self, site: str) -> set[str]:
        widgets = self._site_widgets.get(site)
        if not widgets or not widgets["box"].isChecked():
            return set()
        return {cat for cat, check in widgets["category_checks"].items() if check.isChecked()}

    def _recompute_all(self):
        for site in self._site_widgets:
            self._recompute_site(site)

    def _recompute_site(self, site: str):
        widgets = self._site_widgets.get(site)
        if widgets is None:
            return
        enabled = widgets["box"].isChecked()
        for check in widgets["category_checks"].values():
            check.setEnabled(enabled)
        widgets["add_button"].setEnabled(enabled)

        if not enabled:
            widgets["result_label"].setText("")
            return

        categories = self.selected_categories(site)
        rec = self._wizard_ref.compute_site_recommendation(site, categories)
        if rec.vm_count == 0:
            widgets["result_label"].setText(
                "No Primary VMs match the selected categories - nothing to size."
            )
            return
        widgets["result_label"].setText(
            f"<b>{rec.required_hosts} host(s)</b> for {rec.vm_count} VM(s) "
            f"({rec.hosts_for_cpu} for CPU, {rec.hosts_for_ram} for RAM, "
            f"{rec.binding_constraint} is the limiting factor).<br>"
            f"Storage: {rec.recommended_storage_usable_tb:.1f} TB usable "
            f"({rec.recommended_storage_raw_tb:.1f} TB raw).<br>"
            "<i>Adding this also creates a Failover Assignment for each included VM, "
            "targeting this site, defaulting to the VM's own current size - "
            "adjust individually afterward on the VMs tab if needed.</i>"
        )


# ----------------------------------------------------------------------
# Page 6 - Backup (optional)
# ----------------------------------------------------------------------

class BackupPage(QWizardPage):
    """Optional mini-form for one or more Backup Destinations - fill in
    one, click Add, the form resets so you can add another (e.g. a
    local repo, then an offsite/immutable copy - the two-destination
    shape most of this app's own example projects use for 3-2-1-1).
    Skippable entirely; nothing is required here."""

    def __init__(self, wizard: "ClusterPreparationWizard", parent=None):
        super().__init__(parent)
        self._wizard_ref = wizard
        self.setTitle("Backup")
        self.setSubTitle(
            "Optional - queue one or more backup destinations for the new cluster. "
            "Fill in one, click Add, then fill in another if you want more than one "
            "(e.g. a local repo plus an offsite immutable copy)."
        )

        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

        form_box = QGroupBox("New Backup Destination")
        form = QFormLayout(form_box)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. veeam-repo-primary")
        form.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        form.addRow("Site", self.site_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(DESTINATION_TYPES)
        form.addRow("Type", self.type_combo)

        self.software_edit = QLineEdit()
        self.software_edit.setPlaceholderText("e.g. Veeam, Commvault...")
        form.addRow("Backup Software", self.software_edit)

        self.raw_capacity_spin = QDoubleSpinBox()
        self.raw_capacity_spin.setRange(0.0, 100000.0)
        self.raw_capacity_spin.setSuffix(" TB")
        form.addRow("Raw Capacity", self.raw_capacity_spin)

        self.dedup_spin = QDoubleSpinBox()
        self.dedup_spin.setRange(1.0, 100.0)
        self.dedup_spin.setValue(1.0)
        self.dedup_spin.setSuffix(" : 1")
        form.addRow("Dedup Ratio", self.dedup_spin)

        self.offsite_check = QCheckBox("Offsite")
        form.addRow("", self.offsite_check)

        self.immutable_check = QCheckBox("Immutable")
        form.addRow("", self.immutable_check)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g. Azure Blob Storage - West Europe (optional)")
        form.addRow("Location", self.location_edit)

        add_button = QPushButton("Add This Destination")
        add_button.clicked.connect(self._add_destination)
        form.addRow("", add_button)

        layout.addWidget(form_box)

        self.queued_label = QLabel("No backup destinations queued yet.")
        self.queued_label.setWordWrap(True)
        layout.addWidget(self.queued_label)
        layout.addStretch()

    def initializePage(self):
        current = self.site_combo.currentText()
        self.site_combo.clear()
        self.site_combo.addItems(self._wizard_ref.project.site_names)
        if current in self._wizard_ref.project.site_names:
            self.site_combo.setCurrentText(current)

    def _add_destination(self):
        if not self.name_edit.text().strip():
            QMessageBox.information(self, "Backup", "Give this destination a name first.")
            return

        destination = BackupDestination.create_default()
        destination.name = self.name_edit.text().strip()
        destination.site = self.site_combo.currentText()
        destination.destination_type = self.type_combo.currentText()
        destination.backup_software = self.software_edit.text().strip()
        destination.raw_capacity_tb = self.raw_capacity_spin.value()
        destination.dedup_ratio = self.dedup_spin.value()
        destination.is_offsite = self.offsite_check.isChecked()
        destination.is_immutable = self.immutable_check.isChecked()
        destination.location = self.location_edit.text().strip()
        destination.notes = "Added by Cluster Preparation."

        self._wizard_ref.new_backup_destinations.append(destination)

        names = ", ".join(d.name for d in self._wizard_ref.new_backup_destinations)
        self.queued_label.setText(
            f"<b>{len(self._wizard_ref.new_backup_destinations)} destination(s) queued:</b> {names}.<br>"
            "Nothing has been saved to your project yet - click Finish to actually add them."
        )

        # Reset the form for the next entry, but keep Site (most setups
        # add several destinations at the same site or a natural pair
        # like Primary then DR, so re-picking every time is more friction
        # than it's worth).
        self.name_edit.clear()
        self.software_edit.clear()
        self.raw_capacity_spin.setValue(0.0)
        self.dedup_spin.setValue(1.0)
        self.offsite_check.setChecked(False)
        self.immutable_check.setChecked(False)
        self.location_edit.clear()


class ClusterPreparationWizard(QWizard):
    """Reverse-direction sizing: given the VMs already entered on the VMs
    tab, how many hosts (and how much storage) should you buy? Separate
    calculation from the app's existing oversubscription-ratio checks -
    see src/calculations/cluster_preparation.py's module docstring.
    Next/Next/Finish, not a single crowded form - each page covers one
    decision, and skipping a page just means its sensible default is used.
    The host spec is something WE propose at the end (optimized from your
    actual demand), not something you have to guess up front - see the
    Result page."""

    def __init__(self, project: ClusterProject, parent=None):
        super().__init__(parent)
        self.project = project

        self.setWindowTitle("Cluster Preparation")
        self.resize(640, 620)

        # Explicit button layout: some Qt wizard styles/platforms have
        # been reported to hide the Back button by default - spelling
        # this out guarantees it's always present.
        self.setButtonLayout([
            QWizard.WizardButton.BackButton,
            QWizard.WizardButton.Stretch,
            QWizard.WizardButton.CancelButton,
            QWizard.WizardButton.NextButton,
            QWizard.WizardButton.FinishButton,
        ])

        self.hypervisor_page = HypervisorPage()
        self.workload_page = WorkloadPage(project)
        self.policy_page = PolicyPage()
        self.result_page = ResultPage(self)
        self.additional_sites_page = AdditionalSitesPage(self)
        self.backup_page = BackupPage(self)

        self.addPage(self.hypervisor_page)
        self.addPage(self.workload_page)
        self.addPage(self.policy_page)
        self.addPage(self.result_page)
        self.addPage(self.additional_sites_page)
        self.addPage(self.backup_page)

        self.host_spec_override: HostSpec | None = None

        self.recommended_primary_hosts = 0
        self.recommended_dr_hosts = 0
        self._last_policy: SizingPolicy | None = None
        self._last_primary_host_spec: HostSpec | None = None

        self.new_primary_servers: list[Server] = []
        self.new_primary_storage: list[Storage] = []
        self.new_dr_servers: list[Server] = []
        self.new_dr_storage: list[Storage] = []

        # Generic N-site queues, keyed by site name - populated by
        # add_site_cluster() below, read back by the caller
        # (VirtualMachinesPage._open_cluster_preparation) after the
        # wizard closes, same pattern as the Primary/DR queues above.
        self.new_site_clusters: dict[str, tuple[list[Server], list[Storage]]] = {}
        self.new_failover_assignments: list[FailoverAssignment] = []
        self.new_backup_destinations: list[BackupDestination] = []

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def build_policy(self) -> SizingPolicy:
        vendor_preset = self.hypervisor_page.selected_preset()
        return SizingPolicy(
            ha_level=self.policy_page.ha_combo.currentText(),
            growth_percent=self.policy_page.growth_spin.value(),
            memory_reserve_percent=self.policy_page.reserve_spin.value(),
            storage_overhead_percent=self.policy_page.storage_overhead_spin.value(),
            hypervisor_cpu_reserve_cores=self.policy_page.cpu_reserve_spin.value(),
            assume_hyperthreading=self.policy_page.ht_check.isChecked(),
            host_spec=self.host_spec_override,  # None -> compute_sizing auto-optimizes
            target_cpu_ratio=vendor_preset.thresholds.cpu_warning_ratio * 0.75,
            ratio_overrides=self.workload_page.ratio_overrides(),
        )

    def recompute(self, refill_spec_fields: bool = True):
        policy = self.build_policy()
        try:
            result = compute_sizing(self.project, policy, manual_demand=self.workload_page.manual_demand())
        except Exception as exc:
            report_error(self, "Cluster Preparation", exc)
            self.result_page.result_label.setText(
                "\u26a0 Could not compute a recommendation - see the error dialog for details."
            )
            self.result_page.add_primary_button.setEnabled(False)
            self.result_page.add_dr_button.setEnabled(False)
            return

        self.recommended_primary_hosts = result.required_hosts
        self.recommended_primary_storage_usable_tb = result.recommended_storage_usable_tb
        self.recommended_primary_storage_raw_tb = result.recommended_storage_raw_tb
        self.recommended_dr_hosts = result.dr_required_hosts
        self.recommended_dr_storage_usable_tb = result.dr_recommended_storage_usable_tb
        self.recommended_dr_storage_raw_tb = result.dr_recommended_storage_raw_tb

        self._last_policy = policy
        self._last_primary_host_spec = result.host_spec

        if refill_spec_fields:
            self.result_page.fill_spec_fields(result.host_spec)

        vendor_preset = self.hypervisor_page.selected_preset()

        dr_site_note = ""
        if result.dr_site_vm_count:
            dr_site_note = (
                f" ({result.dr_site_vm_count} more VM(s) already tagged site=DR are "
                "excluded from this count - see the Workload page.)"
            )

        ratio_line = ""
        if result.raw_oversubscription_ratio is not None:
            ratio_line = (
                f"<br>Resulting ratio: {result.total_vcpu_raw} raw vCPU across "
                f"{result.required_hosts} host(s) = {result.raw_oversubscription_ratio:.2f}:1 "
                f"vCPU:pCPU (target was {policy.target_cpu_ratio:.2f}:1 for {vendor_preset.label}, "
                f"warning threshold is {vendor_preset.thresholds.cpu_warning_ratio:.0f}:1)."
            )

        limiting = f"{result.binding_constraint} is the primary sizing constraint."
        dr_limiting = (
            f"{result.dr_binding_constraint} is the DR sizing constraint."
            if result.dr_vm_count else "No DR-protected VMs - nothing to size for DR."
        )

        if result.used_manual_demand:
            vm_count_line = (
                f"<b>Sized from manual entry:</b> {result.total_vcpu_raw} vCPU / "
                f"{result.total_ram_demand_gb:.0f} GB RAM / {result.total_storage_demand_gb / 1024:.1f} TB "
                f"disk (no real VMs on the VMs tab yet - DR sizing isn't available in this mode)."
            )
        else:
            vm_count_line = f"<b>{result.vm_count} Primary VMs.</b>{dr_site_note}"

        self.result_page.result_label.setText(
            f"{vm_count_line}<br><br>"
            f"<b>Primary: {result.required_hosts} host(s)</b> "
            f"({result.hosts_for_cpu} for CPU, {result.hosts_for_ram} for RAM, "
            f"+{result.ha_extra_hosts} for {policy.ha_level}). {limiting}"
            f"{ratio_line}<br>"
            f"Storage: {result.recommended_storage_usable_tb:.1f} TB usable "
            f"({result.recommended_storage_raw_tb:.1f} TB raw with "
            f"{policy.storage_overhead_percent:.0f}% overhead).<br><br>"
            f"<b>DR: {result.dr_required_hosts} host(s)</b> "
            f"({result.dr_vm_count} DR-protected VMs, "
            f"{result.dr_hosts_for_cpu} for CPU, {result.dr_hosts_for_ram} for RAM). "
            f"{dr_limiting}<br>"
            f"DR Storage: {result.dr_recommended_storage_usable_tb:.1f} TB usable "
            f"({result.dr_recommended_storage_raw_tb:.1f} TB raw).<br><br>"
            f"<i>Assumptions: {vendor_preset.label}, {policy.ha_level} HA, "
            f"{policy.growth_percent:.0f}% growth, {policy.memory_reserve_percent:.0f}% "
            f"memory reserve, {policy.storage_overhead_percent:.0f}% storage overhead.</i><br><br>"
        )
        if policy.hypervisor_cpu_reserve_cores > 0:
            self.result_page.result_label.setText(
                self.result_page.result_label.text() +
                f"<b>{policy.hypervisor_cpu_reserve_cores} physical core(s) per host reserved for the "
                f"hypervisor itself</b> - already subtracted from the effective capacity used above, "
                f"not just a note. Adjust on the Policy page if you know your actual footprint differs."
            )
        else:
            self.result_page.result_label.setText(
                self.result_page.result_label.text() +
                "\u26a0 <b>No CPU reserved for the hypervisor itself</b> (RAM still reserves "
                f"{policy.memory_reserve_percent:.0f}% above). Real hypervisors do consume some CPU - "
                "commonly cited around 8-10% overhead for VMware ESXi. Turned off on the Policy page - "
                "set it back above 0 if you'd rather have this reserved automatically."
            )

        self.result_page.add_primary_button.setEnabled(self.recommended_primary_hosts > 0)
        self.result_page.add_dr_button.setEnabled(self.recommended_dr_hosts > 0)

    # ------------------------------------------------------------------
    # Turning the recommendation into real Server/Storage rows
    # ------------------------------------------------------------------

    def _make_servers(self, count: int, site: str, name_prefix: str) -> list[Server]:
        spec = self.result_page.current_spec_fields()
        servers = []
        for i in range(count):
            server = Server.create_default()
            server.name = f"{name_prefix}-{i + 1:02d}"
            server.site = site
            server.sockets = spec.sockets
            server.cores_per_socket = spec.cores_per_socket
            server.threads_per_core = spec.threads_per_core
            server.hyperthreading_enabled = spec.hyperthreading_enabled
            server.ram_gb = int(spec.ram_gb)
            server.notes = "Added by Cluster Preparation - recommended spec, review before ordering."
            servers.append(server)
        return servers

    def _make_storage(self, usable_tb: float, raw_tb: float, site: str, name: str) -> list[Storage]:
        if usable_tb <= 0:
            return []
        storage = Storage.create_default()
        storage.name = name
        storage.site = site
        storage.raw_capacity_tb = round(raw_tb, 2)
        storage.usable_capacity_tb = round(usable_tb, 2)
        storage.raid_overhead_percent = self.policy_page.storage_overhead_spin.value()
        storage.notes = "Added by Cluster Preparation - recommended capacity, review before ordering."
        return [storage]

    def add_primary_cluster(self):
        try:
            self.new_primary_servers = self._make_servers(
                self.recommended_primary_hosts, "Primary", "recommended-p"
            )
            self.new_primary_storage = self._make_storage(
                self.recommended_primary_storage_usable_tb,
                self.recommended_primary_storage_raw_tb,
                "Primary", "recommended-storage-p",
            )
        except Exception as exc:
            self.new_primary_servers = []
            self.new_primary_storage = []
            report_error(self, "Cluster Preparation", exc)
            return
        self._confirm_added("Primary", len(self.new_primary_servers), len(self.new_primary_storage))

    def add_dr_cluster(self):
        try:
            self.new_dr_servers = self._make_servers(
                self.recommended_dr_hosts, "DR", "recommended-dr"
            )
            self.new_dr_storage = self._make_storage(
                self.recommended_dr_storage_usable_tb,
                self.recommended_dr_storage_raw_tb,
                "DR", "recommended-storage-dr",
            )
        except Exception as exc:
            self.new_dr_servers = []
            self.new_dr_storage = []
            report_error(self, "Cluster Preparation", exc)
            return
        self._confirm_added("DR", len(self.new_dr_servers), len(self.new_dr_storage))

    def compute_site_recommendation(self, site: str, categories: set[str]):
        """Wraps the calculation module's function, reusing the CURRENT
        policy and Primary's host spec (computed by the last recompute())
        so every site shares consistent hardware."""
        if self._last_policy is None or self._last_primary_host_spec is None:
            self.recompute(refill_spec_fields=False)
        return compute_site_recommendation_calc(
            self.project, self._last_policy, self._last_primary_host_spec,
            site, categories,
        )

    def add_site_cluster(self, site: str):
        """Queues the recommended servers/storage for this site AND a
        FailoverAssignment for each included VM, targeting this site,
        defaulting to the VM's own current size - one undo step once
        actually committed by the caller after the wizard closes."""
        try:
            categories = self.additional_sites_page.selected_categories(site)
            rec = self.compute_site_recommendation(site, categories)

            servers = self._make_servers(rec.required_hosts, site, f"recommended-{site.lower()}")
            storage = self._make_storage(
                rec.recommended_storage_usable_tb, rec.recommended_storage_raw_tb,
                site, f"recommended-storage-{site.lower()}",
            )
            self.new_site_clusters[site] = (servers, storage)

            vm_by_uid = {vm.uid: vm for vm in self.project.vms}
            new_assignments = []
            for vm_uid in rec.included_vm_uids:
                vm = vm_by_uid.get(vm_uid)
                if vm is None:
                    continue
                assignment = FailoverAssignment.create_default()
                assignment.vm_uid = vm.uid
                assignment.target_site = site
                assignment.vcpu = vm.vcpu
                assignment.ram_gb = vm.ram_gb
                assignment.disk_gb = vm.disk_gb
                new_assignments.append(assignment)
            # Replace any assignments THIS wizard already queued for this
            # site (e.g. re-clicking Add after changing category checkboxes)
            # rather than accumulating duplicates.
            self.new_failover_assignments = [
                a for a in self.new_failover_assignments if a.target_site != site
            ] + new_assignments
        except Exception as exc:
            self.new_site_clusters.pop(site, None)
            report_error(self, "Cluster Preparation", exc)
            return

        QMessageBox.information(
            self, "Queued",
            f"{len(servers)} {site} server(s), {len(storage)} storage system(s), and "
            f"{len(new_assignments)} Failover Assignment(s) queued.\n\n"
            "Nothing has been saved to your project yet - click Finish (bottom of the "
            "wizard) to actually add them.",
        )

    def _confirm_added(self, site: str, server_count: int, storage_count: int):
        QMessageBox.information(
            self,
            "Queued",
            f"{server_count} {site} server(s) and {storage_count} storage system(s) queued.\n\n"
            "Nothing has been saved to your project yet - click Finish (bottom of the "
            "wizard) to actually add them.",
        )
