from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from src.models.backup_destination import BackupDestination


class BackupDestinationTableModel(QAbstractTableModel):

    HEADERS = [
        "Name", "Site", "Type", "Software",
        "Raw (TB)", "Dedup", "Effective (TB)", "Offsite", "Immutable",
    ]

    EDITABLE_COLUMNS = {4, 5}  # Raw capacity, Dedup ratio

    def __init__(
        self,
        destinations: Sequence[BackupDestination] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._destinations = list(destinations) if destinations else []
        self._on_change = on_change

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._destinations)

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

        d = self._destinations[index.row()]
        column = index.column()

        match column:
            case 0:
                return d.name
            case 1:
                return d.site
            case 2:
                return d.destination_type
            case 3:
                return d.backup_software or "-"
            case 4:
                return d.raw_capacity_tb
            case 5:
                return f"{d.dedup_ratio:.1f} : 1"
            case 6:
                return round(d.effective_capacity_tb, 1)
            case 7:
                return "\u2705 Yes" if d.is_offsite else "No"
            case 8:
                return "\u2705 Yes" if d.is_immutable else "No"

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if index.column() not in self.EDITABLE_COLUMNS:
            return False

        d = self._destinations[index.row()]

        try:
            match index.column():
                case 4:
                    d.raw_capacity_tb = max(0.0, float(value))
                case 5:
                    d.dedup_ratio = max(0.1, float(value))
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

    def set_destinations(self, destinations: Sequence[BackupDestination]) -> None:
        self.beginResetModel()
        self._destinations = list(destinations)
        self.endResetModel()

    def destination_at(self, row: int) -> BackupDestination:
        return self._destinations[row]

    def add_destination(self, destination: BackupDestination) -> None:
        self.beginInsertRows(QModelIndex(), len(self._destinations), len(self._destinations))
        self._destinations.append(destination)
        self.endInsertRows()

    def remove_destination(self, row: int) -> None:
        if row < 0 or row >= len(self._destinations):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._destinations.pop(row)
        self.endRemoveRows()

    @property
    def destinations(self) -> list[BackupDestination]:
        return self._destinations
