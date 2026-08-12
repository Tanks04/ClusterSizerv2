from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from src.calculations.cluster_preparation import (
    compute_sizing, SizingPolicy, HostSpec, HA_LEVELS,
)
from src.calculations.thresholds import PRESETS
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.workload_tier import WORKLOAD_TIER_NAMES, WORKLOAD_TIERS

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
        layout.addStretch()

    def initializePage(self):
        primary_vms = self.project.vms_at("Primary")
        dr_site_count = len(self.project.vms_at("DR"))

        if not primary_vms:
            msg = "No VMs on the VMs tab yet - add some there first, with a Workload Tier set on each."
            if dr_site_count:
                msg += f" ({dr_site_count} VM(s) are tagged site=DR and would be excluded from this sizing anyway.)"
            self.summary_label.setText(msg)
            return

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
        self.setSubTitle("If you skip these, sensible defaults are used - N+1, 30% growth, 20% reserve.")

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
            "Applied EQUALLY to vCPU, RAM, and storage demand (not to the vendor "
            "ratio or host count directly). E.g. 30% means the wizard sizes for "
            "30% more of everything than today's VMs actually need - a simple "
            "margin for adding more VMs later, not a prediction of exactly what "
            "will grow."
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

        layout = QVBoxLayout(self)

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
# The wizard itself
# ----------------------------------------------------------------------

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

        self.addPage(self.hypervisor_page)
        self.addPage(self.workload_page)
        self.addPage(self.policy_page)
        self.addPage(self.result_page)

        self.host_spec_override: HostSpec | None = None

        self.recommended_primary_hosts = 0
        self.recommended_dr_hosts = 0

        self.new_primary_servers: list[Server] = []
        self.new_primary_storage: list[Storage] = []
        self.new_dr_servers: list[Server] = []
        self.new_dr_storage: list[Storage] = []

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
            host_spec=self.host_spec_override,  # None -> compute_sizing auto-optimizes
            target_cpu_ratio=vendor_preset.thresholds.cpu_warning_ratio * 0.75,
            ratio_overrides=self.workload_page.ratio_overrides(),
        )

    def recompute(self, refill_spec_fields: bool = True):
        policy = self.build_policy()
        result = compute_sizing(self.project, policy)

        self.recommended_primary_hosts = result.required_hosts
        self.recommended_primary_storage_usable_tb = result.recommended_storage_usable_tb
        self.recommended_primary_storage_raw_tb = result.recommended_storage_raw_tb
        self.recommended_dr_hosts = result.dr_required_hosts
        self.recommended_dr_storage_usable_tb = result.dr_recommended_storage_usable_tb
        self.recommended_dr_storage_raw_tb = result.dr_recommended_storage_raw_tb

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

        self.result_page.result_label.setText(
            f"<b>{result.vm_count} Primary VMs.</b>{dr_site_note}<br><br>"
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
            f"memory reserve, {policy.storage_overhead_percent:.0f}% storage overhead.</i>"
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
        self.new_primary_servers = self._make_servers(
            self.recommended_primary_hosts, "Primary", "recommended-p"
        )
        self.new_primary_storage = self._make_storage(
            self.recommended_primary_storage_usable_tb,
            self.recommended_primary_storage_raw_tb,
            "Primary", "recommended-storage-p",
        )
        self._confirm_added("Primary", len(self.new_primary_servers), len(self.new_primary_storage))

    def add_dr_cluster(self):
        self.new_dr_servers = self._make_servers(
            self.recommended_dr_hosts, "DR", "recommended-dr"
        )
        self.new_dr_storage = self._make_storage(
            self.recommended_dr_storage_usable_tb,
            self.recommended_dr_storage_raw_tb,
            "DR", "recommended-storage-dr",
        )
        self._confirm_added("DR", len(self.new_dr_servers), len(self.new_dr_storage))

    def _confirm_added(self, site: str, server_count: int, storage_count: int):
        self.result_page.result_label.setText(
            self.result_page.result_label.text() +
            f"<br><br><b>{server_count} {site} server(s) and {storage_count} storage "
            "system(s) queued - click Finish, they'll be added to your project.</b>"
        )
