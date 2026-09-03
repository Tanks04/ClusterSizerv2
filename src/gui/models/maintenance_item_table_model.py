from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from src.calculations.pricing import compute_item_status
from src.models.maintenance_item import MaintenanceItem

_STATUS_COLORS = {
    "expired": QColor("#c62828"),        # red
    "expiring_soon": QColor("#ed6c02"),  # orange
    "ok": QColor("#2e7d32"),             # green
    "unknown": None,                     # no expiry date entered - default text color
}

_STATUS_LABELS = {
    "expired": "\u26a0 Expired",
    "expiring_soon": "\u26a0 Expiring soon",
    "ok": "OK",
    "unknown": "-",
}


class MaintenanceItemTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Category", "Applies To", "Cost", "Duration", "Expiry Date", "Status"]

    EDITABLE_COLUMNS = {3, 4}  # Cost, Duration

    def __init__(
        self,
        items: Sequence[MaintenanceItem] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._items = list(items) if items else []
        self._on_change = on_change

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

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

        item = self._items[index.row()]
        column = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            match column:
                case 0:
                    return item.name or "-"
                case 1:
                    return item.category
                case 2:
                    return item.applies_to or "-"
                case 3:
                    return item.cost
                case 4:
                    return item.duration_months
                case 5:
                    return item.expiry_date or "-"
                case 6:
                    return _STATUS_LABELS[compute_item_status(item).status]
            return None

        if role == Qt.ItemDataRole.ForegroundRole and column == 6:
            return _STATUS_COLORS[compute_item_status(item).status]

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if index.column() not in self.EDITABLE_COLUMNS:
            return False

        item = self._items[index.row()]

        try:
            match index.column():
                case 3:
                    item.cost = max(0.0, float(value))
                case 4:
                    item.duration_months = max(1, int(value))
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

    def set_items(self, items: Sequence[MaintenanceItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def item_at(self, row: int) -> MaintenanceItem:
        return self._items[row]

    def add_item(self, item: MaintenanceItem) -> None:
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()

    def remove_item(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._items.pop(row)
        self.endRemoveRows()

    @property
    def items(self) -> list[MaintenanceItem]:
        return self._items
