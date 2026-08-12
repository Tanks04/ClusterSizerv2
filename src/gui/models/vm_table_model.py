from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.virtual_machine import VirtualMachine


class VMTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "vCPU", "Workload", "RAM (GB)", "Disk (GB)", "Power", "DR Protected"]

    EDITABLE_COLUMNS = {2, 4, 5}  # vCPU, RAM, Disk

    def __init__(
        self,
        vms: Sequence[VirtualMachine] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._vms = list(vms) if vms else []
        self._on_change = on_change

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
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        vm = self._vms[index.row()]
        column = index.column()

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
                if vm.dr_protected:
                    return f"✓ {vm.dr_vcpu}vCPU/{vm.dr_ram_gb:.0f}GB/{vm.dr_disk_gb:.0f}GB"
                return "-"

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
