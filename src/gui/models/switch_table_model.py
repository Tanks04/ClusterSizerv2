from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from src.models.network_switch import NetworkSwitch
from src.calculations.networking import switch_port_usage, format_usage, any_over_committed


class SwitchTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "Vendor", "Model", "Type", "Ports (declared)", "Used/Free", "Rack (U)", "Power (W)", "Notes"]

    def __init__(
        self,
        switches: Sequence[NetworkSwitch] | None = None,
        connections_provider: Callable[[], list] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._switches = list(switches) if switches else []
        self._connections_provider = connections_provider or (lambda: [])
        self._on_change = on_change

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._switches)

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

        switch = self._switches[index.row()]
        column = index.column()

        match column:
            case 0:
                return switch.name
            case 1:
                return switch.site
            case 2:
                return switch.vendor
            case 3:
                return switch.model
            case 4:
                return switch.switch_type
            case 5:
                parts = []
                if switch.ports_1g:
                    parts.append(f"1G:{switch.ports_1g}")
                if switch.ports_10g:
                    parts.append(f"10G:{switch.ports_10g}")
                if switch.ports_25g:
                    parts.append(f"25G:{switch.ports_25g}")
                if switch.ports_40g:
                    parts.append(f"40G:{switch.ports_40g}")
                if switch.ports_100g:
                    parts.append(f"100G:{switch.ports_100g}")
                if switch.ports_fc:
                    parts.append(f"FC:{switch.ports_fc}")
                return " ".join(parts) if parts else "-"
            case 6:
                usage = switch_port_usage(switch, self._connections_provider())
                text = format_usage(usage)
                return f"⚠ {text}" if any_over_committed(usage) else text
            case 7:
                return switch.rack_units if switch.rack_units else "-"
            case 8:
                return switch.power_watts if switch.power_watts else "-"
            case 9:
                return switch.notes or "-"

        return None

    def set_switches(self, switches: Sequence[NetworkSwitch]) -> None:
        self.beginResetModel()
        self._switches = list(switches)
        self.endResetModel()

    def switch_at(self, row: int) -> NetworkSwitch:
        return self._switches[row]

    @property
    def switches(self) -> list[NetworkSwitch]:
        return self._switches
