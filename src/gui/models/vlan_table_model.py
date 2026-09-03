from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from src.models.vlan import Vlan


class VlanTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "Network", "Gateway", "VMs", "Notes"]

    def __init__(
        self,
        vlans: Sequence[Vlan] | None = None,
        vms_provider: Callable[[], list] | None = None,
    ):
        super().__init__()
        self._vlans = list(vlans) if vlans else []
        self._vms_provider = vms_provider or (lambda: [])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._vlans)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        vlan = self._vlans[index.row()]
        column = index.column()

        match column:
            case 0:
                return vlan.name or "-"
            case 1:
                return vlan.site
            case 2:
                return vlan.network or "-"
            case 3:
                return vlan.gateway or "-"
            case 4:
                count = sum(1 for vm in self._vms_provider() if vm.vlan_uid == vlan.uid)
                return str(count)
            case 5:
                return vlan.notes or "-"

        return None

    def set_vlans(self, vlans: Sequence[Vlan]) -> None:
        self.beginResetModel()
        self._vlans = list(vlans)
        self.endResetModel()

    def vlan_at(self, row: int) -> Vlan:
        return self._vlans[row]

    @property
    def vlans(self) -> list[Vlan]:
        return self._vlans
