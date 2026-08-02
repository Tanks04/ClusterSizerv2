from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.network_connection import NetworkConnection
from src.models.server import Server
from src.models.network_switch import NetworkSwitch


class ConnectionTableModel(QAbstractTableModel):

    HEADERS = ["Server", "Switch", "Speed", "Media", "Switch Port", "Purpose"]

    def __init__(
        self,
        connections: Sequence[NetworkConnection] | None = None,
        servers_provider: Callable[[], list[Server]] | None = None,
        switches_provider: Callable[[], list[NetworkSwitch]] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._connections = list(connections) if connections else []
        self._servers_provider = servers_provider or (lambda: [])
        self._switches_provider = switches_provider or (lambda: [])
        self._on_change = on_change

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._connections)

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

    def _server_name(self, uid: str) -> str:
        for s in self._servers_provider():
            if s.uid == uid:
                return s.name or "(bez imena)"
        return "⚠ (obrisan server)"

    def _switch_name(self, uid: str) -> str:
        for s in self._switches_provider():
            if s.uid == uid:
                return s.name or "(bez imena)"
        return "⚠ (obrisan switch)"

    def data(self, index, role):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        conn = self._connections[index.row()]
        column = index.column()

        match column:
            case 0:
                return self._server_name(conn.server_uid)
            case 1:
                return self._switch_name(conn.switch_uid)
            case 2:
                return conn.speed
            case 3:
                return conn.media
            case 4:
                return conn.switch_port_label or "-"
            case 5:
                return conn.purpose

        return None

    def set_connections(self, connections: Sequence[NetworkConnection]) -> None:
        self.beginResetModel()
        self._connections = list(connections)
        self.endResetModel()

    def connection_at(self, row: int) -> NetworkConnection:
        return self._connections[row]

    @property
    def connections(self) -> list[NetworkConnection]:
        return self._connections
