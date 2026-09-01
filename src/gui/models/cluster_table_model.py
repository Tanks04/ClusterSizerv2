from typing import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from src.models.cluster import Cluster
from src.calculations.thresholds import Thresholds, Status

_WARNING_COLOR = QColor("#ed6c02")
_CRITICAL_COLOR = QColor("#c62828")


class ClusterTableModel(QAbstractTableModel):

    HEADERS = ["Name", "Site", "Color", "Servers", "VMs", "CPU Ratio", "RAM Utilization", "Notes"]

    def __init__(
        self,
        clusters: Sequence[Cluster] | None = None,
        servers_provider: Callable[[], list] | None = None,
        vms_provider: Callable[[], list] | None = None,
        thresholds_provider: Callable[[], Thresholds] | None = None,
    ):
        super().__init__()
        self._clusters = list(clusters) if clusters else []
        self._servers_provider = servers_provider or (lambda: [])
        self._vms_provider = vms_provider or (lambda: [])
        self._thresholds_provider = thresholds_provider or Thresholds

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._clusters)

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

    def _server_count(self, cluster: Cluster) -> int:
        return sum(1 for s in self._servers_provider() if s.cluster_uid == cluster.uid)

    def _vm_count(self, cluster: Cluster) -> int:
        return sum(1 for v in self._vms_provider() if v.cluster_uid == cluster.uid)

    def _cpu_ratio(self, cluster: Cluster) -> float | None:
        cores = sum(s.effective_cores for s in self._servers_provider() if s.cluster_uid == cluster.uid)
        if cores == 0:
            return None
        demand = sum(
            v.vcpu for v in self._vms_provider()
            if v.cluster_uid == cluster.uid and v.powered_on
        )
        return demand / cores

    def _ram_ratio(self, cluster: Cluster) -> float | None:
        ram = sum(s.ram_gb for s in self._servers_provider() if s.cluster_uid == cluster.uid)
        if ram == 0:
            return None
        demand = sum(
            v.ram_gb for v in self._vms_provider()
            if v.cluster_uid == cluster.uid and v.powered_on
        )
        return demand / ram

    def data(self, index, role):
        if not index.isValid():
            return None

        cluster = self._clusters[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.BackgroundRole and column == 2:
            return QColor(cluster.color)

        if role == Qt.ItemDataRole.ForegroundRole and column in (5, 6):
            thresholds = self._thresholds_provider()
            ratio = self._cpu_ratio(cluster) if column == 5 else self._ram_ratio(cluster)
            if ratio is None:
                return None
            status = thresholds.cpu_status(ratio) if column == 5 else thresholds.ram_status(ratio)
            if status == Status.CRITICAL:
                return _CRITICAL_COLOR
            if status == Status.WARNING:
                return _WARNING_COLOR
            return None

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        match column:
            case 0:
                return cluster.name or "-"
            case 1:
                return cluster.site
            case 2:
                return cluster.color
            case 3:
                return str(self._server_count(cluster))
            case 4:
                return str(self._vm_count(cluster))
            case 5:
                ratio = self._cpu_ratio(cluster)
                if ratio is None:
                    return "-"
                status = self._thresholds_provider().cpu_status(ratio)
                marker = "\u26a0 " if status in (Status.WARNING, Status.CRITICAL) else ""
                return f"{marker}{ratio:.1f} : 1"
            case 6:
                ratio = self._ram_ratio(cluster)
                if ratio is None:
                    return "-"
                status = self._thresholds_provider().ram_status(ratio)
                marker = "\u26a0 " if status in (Status.WARNING, Status.CRITICAL) else ""
                return f"{marker}{ratio * 100:.0f}%"
            case 7:
                return cluster.notes or "-"

        return None

    def set_clusters(self, clusters: Sequence[Cluster]) -> None:
        self.beginResetModel()
        self._clusters = list(clusters)
        self.endResetModel()

    def cluster_at(self, row: int) -> Cluster:
        return self._clusters[row]

    @property
    def clusters(self) -> list[Cluster]:
        return self._clusters
