from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from src.models.virtual_machine import VirtualMachine

# Custom role carrying a border color (or None) for a VM's row - read
# by PassthroughBorderDelegate. A distinct purple, not derived from any
# name-based hash like the switch redundancy border, since the useful
# signal here is simply "this VM has PCI passthrough" rather than
# telling several different passthrough setups apart from each other.
PASSTHROUGH_BORDER_COLOR_ROLE = Qt.ItemDataRole.UserRole
PASSTHROUGH_BORDER_COLOR = "#7c4dff"


class VMTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "vCPU", "Workload", "RAM (GB)", "Disk (GB)", "Power", "DR Category", "Failover Sites", "IP Address", "OS", "VLAN", "Cluster", "Storage Pool", "Notes"]

    EDITABLE_COLUMNS = {2, 4, 5}  # vCPU, RAM, Disk

    def __init__(
        self,
        vms: Sequence[VirtualMachine] | None = None,
        on_change: Callable[[], None] | None = None,
        vlans_provider: Callable[[], list] | None = None,
        failover_assignments_provider: Callable[[], list] | None = None,
        clusters_provider: Callable[[], list] | None = None,
        storages_provider: Callable[[], list] | None = None,
    ):
        super().__init__()
        self._vms = list(vms) if vms else []
        self._on_change = on_change
        self._vlans_provider = vlans_provider or (lambda: [])
        self._failover_assignments_provider = failover_assignments_provider or (lambda: [])
        self._clusters_provider = clusters_provider or (lambda: [])
        self._storages_provider = storages_provider or (lambda: [])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._vms)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() in self.EDITABLE_COLUMNS:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index, role):
        if not index.isValid():
            return None

        vm = self._vms[index.row()]
        column = index.column()

        if role == PASSTHROUGH_BORDER_COLOR_ROLE:
            has_passthrough = any(
                pool.is_passthrough and pool.passthrough_vm_uid == vm.uid
                for storage in self._storages_provider()
                for pool in storage.pools
            )
            return QColor(PASSTHROUGH_BORDER_COLOR) if has_passthrough else None

        if role == Qt.ItemDataRole.BackgroundRole and column == 12 and vm.cluster_uid:
            cluster = next((c for c in self._clusters_provider() if c.uid == vm.cluster_uid), None)
            if cluster:
                return QColor(cluster.color)

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        match column:
            case 0:
                return vm.name
            case 1:
                return vm.site
            case 2:
                return vm.vcpu
            case 3:
                return vm.workload_tier
            case 4:
                return vm.ram_gb
            case 5:
                return vm.disk_gb
            case 6:
                return "On" if vm.powered_on else "Off"
            case 7:
                return vm.dr_category or "-"
            case 8:
                sites = [
                    a.target_site for a in self._failover_assignments_provider()
                    if a.vm_uid == vm.uid
                ]
                return ", ".join(sites) if sites else "-"
            case 9:
                return vm.ip_address or "-"
            case 10:
                return vm.os or "-"
            case 11:
                if not vm.vlan_uid:
                    return "-"
                vlan = next((v for v in self._vlans_provider() if v.uid == vm.vlan_uid), None)
                return vlan.name if vlan else "-"
            case 12:
                if not vm.cluster_uid:
                    return "-"
                cluster = next((c for c in self._clusters_provider() if c.uid == vm.cluster_uid), None)
                return cluster.name if cluster else "-"
            case 13:
                if not vm.storage_uid:
                    return "-"
                storage = next((s for s in self._storages_provider() if s.uid == vm.storage_uid), None)
                return storage.name if storage else "-"
            case 14:
                return vm.notes or "-"

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if index.column() not in self.EDITABLE_COLUMNS:
            return False

        vm = self._vms[index.row()]

        try:
            match index.column():
                case 2:
                    vm.vcpu = max(1, int(value))
                case 4:
                    vm.ram_gb = max(0.1, float(value))
                case 5:
                    vm.disk_gb = max(0.1, float(value))
                case _:
                    return False
        except (TypeError, ValueError):
            return False

        self.dataChanged.emit(
            self.index(index.row(), 0),
            self.index(index.row(), self.columnCount() - 1),
        )

        if self._on_change:
            self._on_change()

        return True

    def set_vms(self, vms: Sequence[VirtualMachine]) -> None:
        self.beginResetModel()
        self._vms = list(vms)
        self.endResetModel()

    def vm_at(self, row: int) -> VirtualMachine:
        return self._vms[row]

    def add_vm(self, vm: VirtualMachine) -> None:
        self.beginInsertRows(QModelIndex(), len(self._vms), len(self._vms))
        self._vms.append(vm)
        self.endInsertRows()

    def remove_vm(self, row: int) -> None:
        if row < 0 or row >= len(self._vms):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._vms.pop(row)
        self.endRemoveRows()

    @property
    def vms(self) -> list[VirtualMachine]:
        return self._vms
