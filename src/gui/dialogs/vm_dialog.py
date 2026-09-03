from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.models.virtual_machine import DR_CATEGORIES, VirtualMachine
from src.models.workload_tier import (
    DEFAULT_WORKLOAD_TIER,
    WORKLOAD_TIER_NAMES,
    WORKLOAD_TIERS,
)
from src.persistence import app_preferences


class VMDialog(QDialog):

    def __init__(self, vm: VirtualMachine | None = None, vlans: list | None = None, storages: list | None = None, clusters: list | None = None, sites: list | None = None, parent=None):
        super().__init__(parent)

        self._vlans = vlans or []
        self._storages = storages or []
        self._clusters = clusters or []

        self.setWindowTitle("Virtual Machine")

        self.resize(400, 480)

        # See ServerDialog for why this is scrollable.
        dialog_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        outer = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        dialog_layout.addWidget(scroll_area)

        layout = QFormLayout()
        self.form_layout = layout
        outer.addLayout(layout)

        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)

        self.site_combo = QComboBox()
        self.site_combo.addItems(sites or ["Primary", "DR"])
        layout.addRow("Site", self.site_combo)

        self.vcpu_spin = QSpinBox()
        self.vcpu_spin.setRange(1, 512)
        self.vcpu_spin.setValue(2)
        layout.addRow("vCPU", self.vcpu_spin)

        self.ram_spin = QDoubleSpinBox()
        self.ram_spin.setDecimals(1)
        self.ram_spin.setRange(0.5, 16384.0)
        self.ram_spin.setSuffix(" GB")
        self.ram_spin.setValue(8.0)
        layout.addRow("RAM", self.ram_spin)

        self.disk_spin = QDoubleSpinBox()
        self.disk_spin.setDecimals(1)
        self.disk_spin.setRange(1.0, 1000000.0)
        self.disk_spin.setSuffix(" GB")
        self.disk_spin.setValue(100.0)
        layout.addRow("Disk", self.disk_spin)

        #
        # Workload profile - feeds Cluster Preparation sizing (see the
        # VirtualMachine docstring). Purely informational/unused by the
        # existing oversubscription-ratio math elsewhere in the app.
        #

        self.workload_combo = QComboBox()
        self.workload_combo.addItems(WORKLOAD_TIER_NAMES)
        self.workload_combo.setCurrentText(DEFAULT_WORKLOAD_TIER)
        self.workload_combo.currentTextChanged.connect(self._update_workload_description)
        layout.addRow("Workload Tier", self.workload_combo)

        self.workload_description_label = QLabel("")
        self.workload_description_label.setWordWrap(True)
        self.workload_description_label.setStyleSheet("color: #757575; font-style: italic;")
        layout.addRow("", self.workload_description_label)
        self._update_workload_description()

        self.powered_check = QCheckBox("Powered on")
        self.powered_check.setChecked(True)
        layout.addRow("", self.powered_check)

        self.ip_address_edit = QLineEdit()
        self.ip_address_edit.setPlaceholderText("e.g. 10.20.1.15 (guest OS IP)")
        layout.addRow("IP Address", self.ip_address_edit)

        self.os_edit = QLineEdit()
        self.os_edit.setPlaceholderText("e.g. Ubuntu Linux (64-bit)")
        layout.addRow("OS", self.os_edit)

        self.vlan_combo = QComboBox()
        self.vlan_combo.addItem("(none)", userData="")
        for vlan in self._vlans:
            label = f"{vlan.name} ({vlan.network})" if vlan.network else vlan.name
            self.vlan_combo.addItem(label, userData=vlan.uid)
        self.vlan_combo.setToolTip(
            "Network segment this VM belongs to - independent of IP Address. "
            "Manage the list on the Network tab."
        )
        layout.addRow("VLAN", self.vlan_combo)
        layout.setRowVisible(self.vlan_combo, app_preferences.load_advanced_mode())

        self.storage_combo = QComboBox()
        self.storage_combo.addItem("(none - site-wide aggregate only)", userData="")
        for storage in self._storages:
            label = f"{storage.name} ({storage.site})"
            self.storage_combo.addItem(label, userData=storage.uid)
        self.storage_combo.setToolTip(
            "Which storage array this VM's disk lives on. Manage the list "
            "on the Storage tab."
        )
        self.storage_combo.currentIndexChanged.connect(self._refresh_storage_pool_combo)
        layout.addRow("Storage Array", self.storage_combo)
        layout.setRowVisible(self.storage_combo, app_preferences.load_advanced_mode())

        self.storage_pool_combo = QComboBox()
        self.storage_pool_combo.setToolTip(
            "Specific pool within the array above, if it's been carved into "
            "several (e.g. SSD tier, SATA tier)."
        )
        layout.addRow("Pool", self.storage_pool_combo)
        self._refresh_storage_pool_combo()

        self.cluster_combo = QComboBox()
        self.cluster_combo.addItem("(none)", userData="")
        for cluster in self._clusters:
            self.cluster_combo.addItem(cluster.name or "(unnamed)", userData=cluster.uid)
        self.cluster_combo.setToolTip(
            "Isolated cluster this VM runs in, for per-cluster CPU/RAM tracking. "
            "Manage the list on the Servers tab."
        )
        layout.addRow("Cluster", self.cluster_combo)
        layout.setRowVisible(self.cluster_combo, app_preferences.load_advanced_mode())

        self.dr_category_combo = QComboBox()
        self.dr_category_combo.setEditable(True)
        self.dr_category_combo.addItems(DR_CATEGORIES)
        self.dr_category_combo.setCurrentText("")
        self.dr_category_combo.setToolTip(
            "Informational - doesn't gate failover. Type your own label if "
            "these don't fit."
        )
        layout.addRow("DR Category", self.dr_category_combo)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(60)
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        dialog_layout.addWidget(buttons)

        self._uid = None

        if vm is not None:
            self.load(vm)

    def _update_workload_description(self) -> None:
        tier = WORKLOAD_TIERS.get(self.workload_combo.currentText())
        if tier:
            self.workload_description_label.setText(
                f"{tier.description} (commonly-cited safe oversubscription: "
                f"{tier.ratio_min:.0f}:1 to {tier.ratio_max:.0f}:1, used as "
                f"{tier.default_ratio:.0f}:1 for sizing - adjustable in Cluster Preparation)."
            )

    def _refresh_storage_pool_combo(self) -> None:
        current_pool_uid = self.storage_pool_combo.currentData()
        self.storage_pool_combo.blockSignals(True)
        self.storage_pool_combo.clear()
        storage_uid = self.storage_combo.currentData()
        storage = next((s for s in self._storages if s.uid == storage_uid), None)
        pools = storage.pools if storage else []
        self.storage_pool_combo.addItem("(none - whole array aggregate)", userData="")
        for pool in pools:
            self.storage_pool_combo.addItem(pool.name or "(unnamed)", userData=pool.uid)
        restored = self.storage_pool_combo.findData(current_pool_uid)
        self.storage_pool_combo.setCurrentIndex(restored if restored >= 0 else 0)
        self.storage_pool_combo.blockSignals(False)

        show_row = app_preferences.load_advanced_mode() and len(pools) > 0
        self.form_layout.setRowVisible(self.storage_pool_combo, show_row)

    def load(self, vm: VirtualMachine) -> None:
        self._uid = vm.uid
        self.name_edit.setText(vm.name)
        self.site_combo.setCurrentText(vm.site)
        self.vcpu_spin.setValue(vm.vcpu)
        self.ram_spin.setValue(vm.ram_gb)
        self.disk_spin.setValue(vm.disk_gb)
        self.powered_check.setChecked(vm.powered_on)
        self.ip_address_edit.setText(vm.ip_address)
        self.os_edit.setText(vm.os)
        vlan_index = self.vlan_combo.findData(vm.vlan_uid)
        self.vlan_combo.setCurrentIndex(vlan_index if vlan_index >= 0 else 0)
        storage_index = self.storage_combo.findData(vm.storage_uid)
        self.storage_combo.setCurrentIndex(storage_index if storage_index >= 0 else 0)
        self._refresh_storage_pool_combo()
        pool_index = self.storage_pool_combo.findData(vm.storage_pool_uid)
        self.storage_pool_combo.setCurrentIndex(pool_index if pool_index >= 0 else 0)
        cluster_index = self.cluster_combo.findData(vm.cluster_uid)
        self.cluster_combo.setCurrentIndex(cluster_index if cluster_index >= 0 else 0)
        self.notes_edit.setPlainText(vm.notes)

        self.workload_combo.setCurrentText(vm.workload_tier)
        self._update_workload_description()

        self.dr_category_combo.setCurrentText(vm.dr_category)

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
        vm.ip_address = self.ip_address_edit.text()
        vm.os = self.os_edit.text()
        vm.vlan_uid = self.vlan_combo.currentData() or ""
        vm.storage_uid = self.storage_combo.currentData() or ""
        vm.storage_pool_uid = self.storage_pool_combo.currentData() or ""
        vm.cluster_uid = self.cluster_combo.currentData() or ""
        vm.notes = self.notes_edit.toPlainText()
        vm.workload_tier = self.workload_combo.currentText()
        vm.dr_category = self.dr_category_combo.currentText()

        return vm
