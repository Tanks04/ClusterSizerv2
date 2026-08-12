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
from src.models.workload_profile import WORKLOAD_PROFILE_NAMES, WORKLOAD_PROFILES


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
        self.setSubTitle("Which platform are you sizing for? Used as a sanity-check reference, not a hard rule.")

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
        self.info_label.setText(
            f"{preset.description} This ratio is shown on the Result page next "
            "to the actual recommendation - not used to override it."
        )

    def selected_preset(self):
        return PRESETS[self.vendor_combo.currentIndex()]


# ----------------------------------------------------------------------
# Page 2 - Workload
# ----------------------------------------------------------------------

class WorkloadPage(QWizardPage):
    """Shows the workload mix already set per-VM on the VMs tab - you
    don't configure utilization percentages here, they come from each
    VM's Workload Profile. The catalog defaults (src/models/
    workload_profile.py) are used as-is unless you explicitly opt into
    fine-tuning them below."""

    def __init__(self, project: ClusterProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.setTitle("Workload")
        self.setSubTitle("Based on the Workload Profile already set per VM on the VMs tab.")

        layout = QVBoxLayout(self)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.utilization_spins: dict[str, QDoubleSpinBox] = {}

        self.util_box = QGroupBox("Fine-tune utilization assumptions (optional)")
        self.util_box.setCheckable(True)
        self.util_box.setChecked(False)
        self.util_box.setToolTip(
            "Off by default - the per-profile defaults below are used as-is. "
            "Check this only if you have real utilization data and want to override them."
        )
        util_form = QFormLayout(self.util_box)

        for name in WORKLOAD_PROFILE_NAMES:
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 100.0)
            spin.setSuffix(" %")
            spin.setValue(WORKLOAD_PROFILES[name].default_cpu_utilization * 100)
            util_form.addRow(name, spin)
            self.utilization_spins[name] = spin

        layout.addWidget(self.util_box)
        layout.addStretch()

    def initializePage(self):
        primary_vms = self.project.vms_at("Primary")
        if not primary_vms:
            self.summary_label.setText(
                "No VMs on the VMs tab yet - add some there first, with a "
                "Workload Profile set on each."
            )
            return

        breakdown: dict[str, int] = {}
        for vm in primary_vms:
            breakdown[vm.workload_profile] = breakdown.get(vm.workload_profile, 0) + 1
        breakdown_text = ", ".join(f"{count} {name}" for name, count in sorted(breakdown.items()))
        self.summary_label.setText(
            f"{len(primary_vms)} VMs: {breakdown_text}.\n\n"
            "Each profile's default utilization assumption:\n" +
            "\n".join(
                f"  \u2022 {name}: {WORKLOAD_PROFILES[name].default_cpu_utilization * 100:.0f}%"
                for name in WORKLOAD_PROFILE_NAMES
            )
        )

    def utilization_overrides(self) -> dict[str, float]:
        if not self.util_box.isChecked():
            return {}
        return {name: spin.value() / 100 for name, spin in self.utilization_spins.items()}


# ----------------------------------------------------------------------
# Page 3 - Policy
# ----------------------------------------------------------------------

class PolicyPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Policy")
        self.setSubTitle("If you skip these, sensible defaults are used - N+1, no growth, 20% reserve.")

        layout = QFormLayout(self)

        self.ha_combo = QComboBox()
        self.ha_combo.addItems(HA_LEVELS)
        self.ha_combo.setCurrentText("N+1")
        layout.addRow("High Availability", self.ha_combo)

        self.growth_spin = QDoubleSpinBox()
        self.growth_spin.setRange(0.0, 500.0)
        self.growth_spin.setSuffix(" %")
        self.growth_spin.setValue(0.0)
        self.growth_spin.setToolTip("Expected growth in demand over your planning period.")
        layout.addRow("Expected Growth", self.growth_spin)

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


# ----------------------------------------------------------------------
# Page 4 - Candidate host spec
# ----------------------------------------------------------------------

class HostSpecPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Candidate Host Spec")
        self.setSubTitle("What you're sizing against - the Result page tells you how many of these you need.")

        layout = QFormLayout(self)

        self.sockets_spin = QSpinBox()
        self.sockets_spin.setRange(1, 8)
        self.sockets_spin.setValue(2)
        layout.addRow("Sockets", self.sockets_spin)

        self.cores_spin = QSpinBox()
        self.cores_spin.setRange(1, 256)
        self.cores_spin.setValue(24)
        layout.addRow("Cores / Socket", self.cores_spin)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 4)
        self.threads_spin.setValue(2)
        layout.addRow("Threads / Core", self.threads_spin)

        self.ht_check = QCheckBox("Hyperthreading Enabled")
        self.ht_check.setChecked(True)
        layout.addRow("", self.ht_check)

        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(16, 32768)
        self.ram_spin.setSuffix(" GB")
        self.ram_spin.setValue(512)
        layout.addRow("RAM / Host", self.ram_spin)

    def host_spec(self) -> HostSpec:
        return HostSpec(
            sockets=self.sockets_spin.value(),
            cores_per_socket=self.cores_spin.value(),
            threads_per_core=self.threads_spin.value(),
            hyperthreading_enabled=self.ht_check.isChecked(),
            ram_gb=float(self.ram_spin.value()),
        )


# ----------------------------------------------------------------------
# Page 5 - Result
# ----------------------------------------------------------------------

class SummaryPage(QWizardPage):
    def __init__(self, wizard: "ClusterPreparationWizard", parent=None):
        super().__init__(parent)
        self._wizard_ref = wizard
        self.setTitle("Result")
        self.setSubTitle("Every number below is an assumption-driven estimate, not a guarantee.")

        layout = QVBoxLayout(self)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

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
    decision, and skipping a page just means its sensible default is used."""

    def __init__(self, project: ClusterProject, parent=None):
        super().__init__(parent)
        self.project = project

        self.setWindowTitle("Cluster Preparation")
        self.resize(640, 560)

        self.hypervisor_page = HypervisorPage()
        self.workload_page = WorkloadPage(project)
        self.policy_page = PolicyPage()
        self.host_page = HostSpecPage()
        self.summary_page = SummaryPage(self)

        self.addPage(self.hypervisor_page)
        self.addPage(self.workload_page)
        self.addPage(self.policy_page)
        self.addPage(self.host_page)
        self.addPage(self.summary_page)

        self.recommended_primary_hosts = 0
        self.recommended_dr_hosts = 0

        self.new_primary_servers: list[Server] = []
        self.new_primary_storage: list[Storage] = []
        self.new_dr_servers: list[Server] = []
        self.new_dr_storage: list[Storage] = []

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def build_policy(self, ht_override: bool | None = None) -> SizingPolicy:
        host_spec = self.host_page.host_spec()
        if ht_override is not None:
            host_spec = HostSpec(
                sockets=host_spec.sockets,
                cores_per_socket=host_spec.cores_per_socket,
                threads_per_core=host_spec.threads_per_core,
                hyperthreading_enabled=ht_override,
                ram_gb=host_spec.ram_gb,
            )
        return SizingPolicy(
            ha_level=self.policy_page.ha_combo.currentText(),
            growth_percent=self.policy_page.growth_spin.value(),
            memory_reserve_percent=self.policy_page.reserve_spin.value(),
            storage_overhead_percent=self.policy_page.storage_overhead_spin.value(),
            host_spec=host_spec,
            utilization_overrides=self.workload_page.utilization_overrides(),
        )

    def recompute(self):
        policy = self.build_policy()
        result = compute_sizing(self.project, policy)

        self.recommended_primary_hosts = result.required_hosts
        self.recommended_primary_storage_usable_tb = result.recommended_storage_usable_tb
        self.recommended_primary_storage_raw_tb = result.recommended_storage_raw_tb
        self.recommended_dr_hosts = result.dr_required_hosts
        self.recommended_dr_storage_usable_tb = result.dr_recommended_storage_usable_tb
        self.recommended_dr_storage_raw_tb = result.dr_recommended_storage_raw_tb

        vendor_preset = self.hypervisor_page.selected_preset()
        ratio_line = ""
        if result.raw_oversubscription_ratio is not None:
            ratio_line = (
                f"<br>Sanity check: {result.total_vcpu_raw} raw vCPU across "
                f"{result.required_hosts} host(s) = {result.raw_oversubscription_ratio:.2f}:1 "
                f"vCPU:pCPU - {vendor_preset.label} guidance is a starting point around "
                f"{vendor_preset.thresholds.cpu_warning_ratio:.0f}:1, so this "
                f"{'is comfortably under' if result.raw_oversubscription_ratio <= vendor_preset.thresholds.cpu_warning_ratio else 'is ABOVE'} "
                "that reference."
            )

        ht_hint = self._hyperthreading_hint(policy, result)

        limiting = f"{result.binding_constraint} is the primary sizing constraint."
        dr_limiting = (
            f"{result.dr_binding_constraint} is the DR sizing constraint."
            if result.dr_vm_count else "No DR-protected VMs - nothing to size for DR."
        )

        self.summary_page.result_label.setText(
            f"<b>Primary: {result.required_hosts} host(s)</b> "
            f"({result.hosts_for_cpu} for CPU, {result.hosts_for_ram} for RAM, "
            f"+{result.ha_extra_hosts} for {policy.ha_level}). {limiting}"
            f"{ratio_line}<br>"
            f"Storage: {result.recommended_storage_usable_tb:.1f} TB usable "
            f"({result.recommended_storage_raw_tb:.1f} TB raw with "
            f"{policy.storage_overhead_percent:.0f}% overhead).<br>"
            f"{ht_hint}<br><br>"
            f"<b>DR: {result.dr_required_hosts} host(s)</b> "
            f"({result.dr_vm_count} DR-protected VMs, "
            f"{result.dr_hosts_for_cpu} for CPU, {result.dr_hosts_for_ram} for RAM). "
            f"{dr_limiting}<br>"
            f"DR Storage: {result.dr_recommended_storage_usable_tb:.1f} TB usable "
            f"({result.dr_recommended_storage_raw_tb:.1f} TB raw).<br><br>"
            f"<i>Assumptions: {vendor_preset.label}, {policy.ha_level} HA, "
            f"{policy.growth_percent:.0f}% growth, {policy.memory_reserve_percent:.0f}% "
            f"memory reserve, {policy.storage_overhead_percent:.0f}% storage overhead, host = "
            f"{policy.host_spec.sockets}x{policy.host_spec.cores_per_socket}-core "
            f"({policy.host_spec.effective_cores} effective cores), "
            f"{policy.host_spec.ram_gb:.0f} GB RAM/host.</i>"
        )

        self.summary_page.add_primary_button.setEnabled(self.recommended_primary_hosts > 0)
        self.summary_page.add_dr_button.setEnabled(self.recommended_dr_hosts > 0)

    def _hyperthreading_hint(self, policy: SizingPolicy, result) -> str:
        """Computed, not guessed: actually re-runs sizing with HT flipped
        and reports the real difference - only shown when it would
        actually change the host count."""
        current_ht = policy.host_spec.hyperthreading_enabled
        alt_policy = self.build_policy(ht_override=not current_ht)
        alt_result = compute_sizing(self.project, alt_policy)

        if alt_result.required_hosts == result.required_hosts:
            return ""

        if current_ht:
            return (
                f"\U0001f4a1 Disabling Hyperthreading would raise Primary from "
                f"{result.required_hosts} to {alt_result.required_hosts} host(s) - "
                "keeping it on is saving you capacity here."
            )
        return (
            f"\U0001f4a1 Enabling Hyperthreading would lower Primary from "
            f"{result.required_hosts} to {alt_result.required_hosts} host(s) - "
            "worth it unless this workload is latency-sensitive."
        )

    # ------------------------------------------------------------------
    # Turning the recommendation into real Server/Storage rows
    # ------------------------------------------------------------------

    def _make_servers(self, count: int, site: str, name_prefix: str) -> list[Server]:
        policy = self.build_policy()
        servers = []
        for i in range(count):
            server = Server.create_default()
            server.name = f"{name_prefix}-{i + 1:02d}"
            server.site = site
            server.sockets = policy.host_spec.sockets
            server.cores_per_socket = policy.host_spec.cores_per_socket
            server.threads_per_core = policy.host_spec.threads_per_core
            server.hyperthreading_enabled = policy.host_spec.hyperthreading_enabled
            server.ram_gb = int(policy.host_spec.ram_gb)
            server.notes = "Added by Cluster Preparation - recommended spec, review before ordering."
            servers.append(server)
        return servers

    def _make_storage(self, usable_tb: float, raw_tb: float, site: str, name: str) -> list[Storage]:
        if usable_tb <= 0:
            return []
        policy = self.build_policy()
        storage = Storage.create_default()
        storage.name = name
        storage.site = site
        storage.raw_capacity_tb = round(raw_tb, 2)
        storage.usable_capacity_tb = round(usable_tb, 2)
        storage.raid_overhead_percent = policy.storage_overhead_percent
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
        self.summary_page.result_label.setText(
            self.summary_page.result_label.text() +
            f"<br><br><b>{server_count} {site} server(s) and {storage_count} storage "
            "system(s) queued - click Finish, they'll be added to your project as one action.</b>"
        )

    def get_new_servers(self) -> list[Server]:
        """Called by the VMs page after the wizard closes - returns
        whatever server rows were queued via the Add buttons (empty if
        the user never clicked either)."""
        return self.new_primary_servers + self.new_dr_servers

    def get_new_storages(self) -> list[Storage]:
        """Same as get_new_servers(), for the storage rows queued alongside."""
        return self.new_primary_storage + self.new_dr_storage
