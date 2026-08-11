from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.server import Server


class ServerTableModel(QAbstractTableModel):

    HEADERS = [
        "Name", "Site", "Vendor", "Model", "CPU",
        "Sockets", "Cores/Socket", "Threads/Core", "HT",
        "Total Cores", "Effective Cores",
        "RAM (GB)", "GHz", "Warranty",
    ]

    # Kolone koje se mogu direktno urediti u tablici (bez otvaranja dijaloga)
    EDITABLE_COLUMNS = {5, 6, 7, 11, 12}  # Sockets, Cores/Socket, Threads/Core, RAM, GHz

    def __init__(
        self,
        servers: Sequence[Server] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()

        self._servers = list(servers) if servers else []
        self._on_change = on_change

    # ---------------------------------------------------------
    # Qt mandatory methods
    # ---------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._servers)

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

        server = self._servers[index.row()]
        column = index.column()

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        match column:
            case 0:
                return server.name
            case 1:
                return server.site
            case 2:
                return server.vendor
            case 3:
                return server.model
            case 4:
                return server.cpu_model
            case 5:
                return server.sockets
            case 6:
                return server.cores_per_socket
            case 7:
                return server.threads_per_core
            case 8:
                return "On" if server.hyperthreading_enabled else "Off"
            case 9:
                return server.total_cores
            case 10:
                return server.effective_cores
            case 11:
                return server.ram_gb
            case 12:
                return server.cpu_frequency
            case 13:
                return server.warranty_expiry or "-"

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        if index.column() not in self.EDITABLE_COLUMNS:
            return False

        server = self._servers[index.row()]

        try:
            match index.column():
                case 5:
                    server.sockets = max(1, int(value))
                case 6:
                    server.cores_per_socket = max(1, int(value))
                case 7:
                    server.threads_per_core = max(1, int(value))
                case 11:
                    server.ram_gb = max(1, int(value))
                case 12:
                    server.cpu_frequency = max(0.1, float(value))
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

    # ---------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------

    def set_servers(self, servers: Sequence[Server]) -> None:
        self.beginResetModel()
        self._servers = list(servers)
        self.endResetModel()

    def server_at(self, row: int) -> Server:
        return self._servers[row]

    def add_server(self, server: Server) -> None:
        self.beginInsertRows(QModelIndex(), len(self._servers), len(self._servers))
        self._servers.append(server)
        self.endInsertRows()

    def remove_server(self, row: int) -> None:
        if row < 0 or row >= len(self._servers):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._servers.pop(row)
        self.endRemoveRows()

    @property
    def servers(self) -> list[Server]:
        return self._servers
