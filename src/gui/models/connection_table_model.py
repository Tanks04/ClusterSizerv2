from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from src.models.network_connection import NetworkConnection
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.storage import Storage


class ConnectionTableModel(QAbstractTableModel):

    HEADERS = ["Type", "Endpoint A", "Endpoint B", "Speed", "Media", "Port Label", "Purpose"]

    def __init__(
        self,
        connections: Sequence[NetworkConnection] | None = None,
        servers_provider: Callable[[], list[Server]] | None = None,
        switches_provider: Callable[[], list[NetworkSwitch]] | None = None,
        storages_provider: Callable[[], list[Storage]] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._connections = list(connections) if connections else []
        self._servers_provider = servers_provider or (lambda: [])
        self._switches_provider = switches_provider or (lambda: [])
        self._storages_provider = storages_provider or (lambda: [])
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

    def _name_for(self, uid: str, provider, missing_label: str) -> str:
        for entity in provider():
            if entity.uid == uid:
                return entity.name or "(unnamed)"
        return f"\u26a0 ({missing_label})"

    def _endpoint_label(self, uid_field: str, uid: str) -> str:
        if uid_field == "server_uid":
            return self._name_for(uid, self._servers_provider, "deleted server")
        if uid_field == "switch_uid":
            return self._name_for(uid, self._switches_provider, "deleted switch")
        return self._name_for(uid, self._storages_provider, "deleted storage")

    def _endpoints(self, conn: NetworkConnection) -> tuple[str, str]:
        """Returns (Endpoint A text, Endpoint B text) - whichever two of
        (server_uid, switch_uid, storage_uid) are populated, in a
        consistent order (Server/Storage first, Switch/Storage second)."""
        filled = [
            (field, getattr(conn, field))
            for field in ("server_uid", "switch_uid", "storage_uid")
            if getattr(conn, field)
        ]
        if len(filled) != 2:
            return ("\u26a0 (incomplete)", "\u26a0 (incomplete)")
        (field_a, uid_a), (field_b, uid_b) = filled
        return (self._endpoint_label(field_a, uid_a), self._endpoint_label(field_b, uid_b))

    def data(self, index, role):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        conn = self._connections[index.row()]
        column = index.column()

        match column:
            case 0:
                return conn.connection_kind
            case 1:
                return self._endpoints(conn)[0]
            case 2:
                return self._endpoints(conn)[1]
            case 3:
                return conn.speed
            case 4:
                return conn.media
            case 5:
                return conn.switch_port_label or "-"
            case 6:
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
