from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.models.storage import StoragePool


class StoragePoolDialog(QDialog):
    """One carved-out slice of a Storage array's disks - a fast SSD
    tier, a bulk SATA tier, or a pool zoned to a specific set of
    servers. The server checklist mirrors StorageDialog's own HCI
    server list: which servers this pool is presented to (zoning/
    masking), purely informational for capacity math - a VM picks a
    specific pool via its own Storage Pool field once one exists here."""

    def __init__(self, pool: StoragePool | None = None, servers: list | None = None, vms: list | None = None, service=None, parent=None):
        super().__init__(parent)
        self._servers = servers or []
        self._vms = vms or []
        self._service = service

        self.setWindowTitle("Storage Pool")
        self.resize(420, 480)

        layout = QFormLayout(self)
        self.form_layout = layout

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. SSD-Tier, SATA-Tier, App-Servers-Pool...")
        layout.addRow("Name", self.name_edit)

        self.raid_calc_button = QPushButton("Open RAID Calculator...")
        self.raid_calc_button.setToolTip(
            "Full RAID sizing, pre-loaded with this pool's own disk count if "
            "already saved - e.g. add 4 more disks to expand it."
        )
        self.raid_calc_button.clicked.connect(self._open_raid_calculator)
        layout.addRow("", self.raid_calc_button)

        self.raw_spin = QDoubleSpinBox()
        self.raw_spin.setDecimals(2)
        self.raw_spin.setRange(0.0, 100000.0)
        self.raw_spin.setSuffix(" TB")
        layout.addRow("Raw Capacity", self.raw_spin)

        self.usable_spin = QDoubleSpinBox()
        self.usable_spin.setDecimals(2)
        self.usable_spin.setRange(0.0, 100000.0)
        self.usable_spin.setSuffix(" TB")
        layout.addRow("Usable Capacity", self.usable_spin)

        self.passthrough_check = QCheckBox("PCI Passthrough (bypasses the hypervisor, direct to one VM)")
        self.passthrough_check.setToolTip(
            "Wired directly to ONE VM instead of zoned to hosts - the "
            "cluster/hosts never see this pool at all."
        )
        self.passthrough_check.toggled.connect(self._on_passthrough_toggled)
        layout.addRow("", self.passthrough_check)

        self.passthrough_vm_combo = QComboBox()
        self.passthrough_vm_combo.addItem("(none)", userData="")
        for vm in self._vms:
            self.passthrough_vm_combo.addItem(f"{vm.name} ({vm.site})", userData=vm.uid)
        layout.addRow("Connected VM", self.passthrough_vm_combo)

        servers_box = QGroupBox("Zoned Servers (optional)")
        self._servers_box = servers_box
        servers_layout = QVBoxLayout(servers_box)
        self.servers_list = QListWidget()
        self.servers_list.setMinimumHeight(140)
        self.servers_list.setMaximumHeight(200)
        for server in self._servers:
            item = QListWidgetItem(f"{server.name} ({server.site})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, server.uid)
            self.servers_list.addItem(item)
        servers_layout.addWidget(self.servers_list)
        layout.addRow(servers_box)
        self._on_passthrough_toggled(False)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(60)
        layout.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._uid = None
        self._loaded_disk_count = 0
        self._loaded_disk_size_tb = 0.0
        self._loaded_raid_level = ""
        if pool is not None:
            self.load(pool)

    def _on_passthrough_toggled(self, checked: bool) -> None:
        self.form_layout.setRowVisible(self.passthrough_vm_combo, checked)
        self.form_layout.setRowVisible(self._servers_box, not checked)

    def _open_raid_calculator(self) -> None:
        if self._service is None:
            QMessageBox.information(
                self, "RAID Calculator",
                "Open this from the Storage tab so it can find this project's data.",
            )
            return
        from src.gui.dialogs.raid_calculator_dialog import RaidCalculatorDialog
        dialog = RaidCalculatorDialog(self._service, parent=self)
        if self._uid:
            idx = dialog.target_type_combo.findText("Storage Pool")
            dialog.target_type_combo.setCurrentIndex(idx)
            for i in range(dialog.target_entity_combo.count()):
                storage_index, pool_index = dialog.target_entity_combo.itemData(i)
                if self._service.project.storages[storage_index].pools[pool_index].uid == self._uid:
                    dialog.target_entity_combo.setCurrentIndex(i)
                    break
        dialog.exec()

        if self._uid:
            for storage in self._service.project.storages:
                for pool in storage.pools:
                    if pool.uid == self._uid:
                        self.raw_spin.setValue(pool.raw_capacity_tb)
                        self.usable_spin.setValue(pool.usable_capacity_tb)
                        self._loaded_disk_count = pool.disk_count
                        self._loaded_disk_size_tb = pool.disk_size_tb
                        self._loaded_raid_level = pool.raid_level
                        return

    def load(self, pool: StoragePool) -> None:
        self._uid = pool.uid
        self._loaded_disk_count = pool.disk_count
        self._loaded_disk_size_tb = pool.disk_size_tb
        self._loaded_raid_level = pool.raid_level
        self.name_edit.setText(pool.name)
        self.raw_spin.setValue(pool.raw_capacity_tb)
        self.usable_spin.setValue(pool.usable_capacity_tb)
        self.passthrough_check.setChecked(pool.is_passthrough)
        vm_index = self.passthrough_vm_combo.findData(pool.passthrough_vm_uid)
        self.passthrough_vm_combo.setCurrentIndex(vm_index if vm_index >= 0 else 0)
        for i in range(self.servers_list.count()):
            item = self.servers_list.item(i)
            server_uid = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(
                Qt.CheckState.Checked if server_uid in pool.server_uids else Qt.CheckState.Unchecked
            )
        self.notes_edit.setPlainText(pool.notes)

    def get_pool(self) -> StoragePool:
        import uuid
        pool_uid = self._uid or str(uuid.uuid4())
        return StoragePool(
            uid=pool_uid,
            name=self.name_edit.text(),
            raw_capacity_tb=self.raw_spin.value(),
            usable_capacity_tb=self.usable_spin.value(),
            server_uids=[
                self.servers_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.servers_list.count())
                if self.servers_list.item(i).checkState() == Qt.CheckState.Checked
            ],
            notes=self.notes_edit.toPlainText(),
            is_passthrough=self.passthrough_check.isChecked(),
            passthrough_vm_uid=self.passthrough_vm_combo.currentData() or "",
            disk_count=self._loaded_disk_count,
            disk_size_tb=self._loaded_disk_size_tb,
            raid_level=self._loaded_raid_level,
        )
