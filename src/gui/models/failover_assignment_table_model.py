from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from src.models.failover_assignment import FailoverAssignment

_STALE_COLOR = QColor("#e65100")  # matches the Attention panel's Warning color


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

    @staticmethod
    def _stale_columns(assignment: FailoverAssignment, vm) -> set[int]:
        """Only an assignment field that EXCEEDS the VM's current value
        counts as stale - a smaller footprint is the normal, intentional
        pattern for a budget/constrained failover target and must never
        be flagged (see compute_attention_items, which applies this
        exact same rule for the Attention Needed panel). Column-specific
        rather than whole-row, so a vCPU mismatch alone doesn't also
        mark RAM/Disk that are perfectly in sync."""
        stale = set()
        if assignment.vcpu > vm.vcpu:
            stale.add(2)
        if assignment.ram_gb > vm.ram_gb:
            stale.add(3)
        if assignment.disk_gb > vm.disk_gb:
            stale.add(4)
        return stale

    def data(self, index, role):
        if not index.isValid():
            return None

        assignment = self._assignments[index.row()]
        column = index.column()
        vm = next((v for v in self._vms_provider() if v.uid == assignment.vm_uid), None)
        stale_columns = (
            self._stale_columns(assignment, vm)
            if vm is not None and not assignment.footprint_confirmed
            else set()
        )

        if role == Qt.ItemDataRole.ForegroundRole and column in stale_columns:
            return _STALE_COLOR

        if role == Qt.ItemDataRole.ToolTipRole and column in stale_columns:
            return (
                f"This exceeds {vm.name}'s current size ({vm.vcpu} vCPU/"
                f"{vm.ram_gb:.0f} GB/{vm.disk_gb:.0f} GB) - the VM may have "
                "been resized since this assignment was created or last updated."
            )

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        marker = "\u26a0 " if column in stale_columns else ""

        match column:
            case 0:
                return vm.name if vm else "(deleted VM)"
            case 1:
                return assignment.target_site
            case 2:
                return f"{marker}{assignment.vcpu}"
            case 3:
                return f"{marker}{assignment.ram_gb:.1f}"
            case 4:
                return f"{marker}{assignment.disk_gb:.1f}"

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
