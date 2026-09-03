from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from src.calculations.networking import (
    any_over_committed,
    format_usage,
    switch_port_usage,
)
from src.models.network_switch import NetworkSwitch, redundancy_group_color

# Custom role carrying the redundancy border color (or None) for a row -
# read by RedundancyBorderDelegate via index.data(...), which Qt
# resolves correctly whether the view goes through this model directly
# or through a QSortFilterProxyModel wrapping it.
REDUNDANCY_BORDER_COLOR_ROLE = Qt.ItemDataRole.UserRole


class SwitchTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "Vendor", "Model", "Type", "Redundancy", "Ports (declared)", "Used/Free", "Rack (U)", "Power (W)", "Notes"]

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
        if not index.isValid():
            return None

        switch = self._switches[index.row()]
        column = index.column()

        if role == REDUNDANCY_BORDER_COLOR_ROLE:
            color = redundancy_group_color(switch.redundancy_group)
            return QColor(color) if color else None

        if role != Qt.ItemDataRole.DisplayRole:
            return None

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
                if not switch.redundancy_group:
                    return "-"
                role_suffix = f" ({switch.redundancy_role})" if switch.redundancy_role else ""
                return f"{switch.redundancy_group}{role_suffix}"
            case 6:
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
            case 7:
                usage = switch_port_usage(switch, self._connections_provider())
                text = format_usage(usage)
                return f"⚠ {text}" if any_over_committed(usage) else text
            case 8:
                return switch.rack_units if switch.rack_units else "-"
            case 9:
                return switch.power_watts if switch.power_watts else "-"
            case 10:
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
