from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.storage import Storage


class StorageTableModel(QAbstractTableModel):

    HEADERS = [
        "Name", "Site", "Vendor", "Model",
        "Raw (TB)", "Usable (TB)", "Overhead %",
    ]

    EDITABLE_COLUMNS = {4, 5}  # Raw, Usable

    def __init__(
        self,
        storages: Sequence[Storage] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._storages = list(storages) if storages else []
        self._on_change = on_change

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._storages)

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

        storage = self._storages[index.row()]
        column = index.column()

        match column:
            case 0:
                return storage.name
            case 1:
                return storage.site
            case 2:
                return storage.vendor
            case 3:
                return storage.model
            case 4:
                return storage.raw_capacity_tb
            case 5:
                return storage.usable_capacity_tb
            case 6:
                return round(storage.raid_overhead_percent, 1)

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if index.column() not in self.EDITABLE_COLUMNS:
            return False

        storage = self._storages[index.row()]

        try:
            match index.column():
                case 4:
                    storage.raw_capacity_tb = max(0.0, float(value))
                case 5:
                    storage.usable_capacity_tb = max(0.0, float(value))
                case _:
                    return False
        except (TypeError, ValueError):
            return False

        if storage.raw_capacity_tb > 0:
            storage.raid_overhead_percent = max(
                0.0, (1 - storage.usable_capacity_tb / storage.raw_capacity_tb) * 100
            )

        self.dataChanged.emit(
            self.index(index.row(), 0),
            self.index(index.row(), self.columnCount() - 1),
        )

        if self._on_change:
            self._on_change()

        return True

    def set_storages(self, storages: Sequence[Storage]) -> None:
        self.beginResetModel()
        self._storages = list(storages)
        self.endResetModel()

    def storage_at(self, row: int) -> Storage:
        return self._storages[row]

    def add_storage(self, storage: Storage) -> None:
        self.beginInsertRows(QModelIndex(), len(self._storages), len(self._storages))
        self._storages.append(storage)
        self.endInsertRows()

    def remove_storage(self, row: int) -> None:
        if row < 0 or row >= len(self._storages):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._storages.pop(row)
        self.endRemoveRows()

    @property
    def storages(self) -> list[Storage]:
        return self._storages
