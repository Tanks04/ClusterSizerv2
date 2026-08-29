from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.failover_assignment import FailoverAssignment


class FailoverAssignmentTableModel(QAbstractTableModel):

    HEADERS = ["VM", "Target Site", "vCPU", "RAM (GB)", "Disk (GB)"]

    def __init__(
        self,
        assignments: Sequence[FailoverAssignment] | None = None,
        vms_provider: Callable[[], list] | None = None,
    ):
        super().__init__()
        self._assignments = list(assignments) if assignments else []
        self._vms_provider = vms_provider or (lambda: [])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._assignments)

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

        assignment = self._assignments[index.row()]
        column = index.column()

        match column:
            case 0:
                vm = next((v for v in self._vms_provider() if v.uid == assignment.vm_uid), None)
                return vm.name if vm else "(deleted VM)"
            case 1:
                return assignment.target_site
            case 2:
                return str(assignment.vcpu)
            case 3:
                return f"{assignment.ram_gb:.1f}"
            case 4:
                return f"{assignment.disk_gb:.1f}"

        return None

    def set_assignments(self, assignments: Sequence[FailoverAssignment]) -> None:
        self.beginResetModel()
        self._assignments = list(assignments)
        self.endResetModel()

    def assignment_at(self, row: int) -> FailoverAssignment:
        return self._assignments[row]

    @property
    def assignments(self) -> list[FailoverAssignment]:
        return self._assignments
