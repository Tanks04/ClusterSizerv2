from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.persistence import csv_io, project_repository


class ProjectService(QObject):
    """Central service class for working with the active project.

    `changed` is the general signal (for Dashboard/Summary/Reports/window
    title - pages that need to know about ANY change). servers_changed /
    storages_changed / vms_changed / network_changed are narrower signals -
    each CRUD table subscribes to ONLY its own, so it doesn't run
    beginResetModel() on tables whose data hasn't changed at all. This
    isn't just about performance: a large number of unnecessary model
    resets at once (e.g. adding one Storage entry resetting everything
    from Servers to Network) increases the chance of hitting a
    timing-sensitive Qt/PySide bug (see ROADMAP - a Windows crash tied to
    QHeaderView.ResizeToContents).
    """

    changed = Signal()

    servers_changed = Signal()
    storages_changed = Signal()
    vms_changed = Signal()
    network_changed = Signal()  # switches + connections zajedno

    def __init__(self) -> None:
        super().__init__()
        self._project = ClusterProject()
        self._thresholds = Thresholds()
        self._current_path: Path | None = None
        self._dirty = False

    # ------------------------------------------------------------------
    # Osnovno stanje
    # ------------------------------------------------------------------

    @property
    def project(self) -> ClusterProject:
        return self._project

    @property
    def thresholds(self) -> Thresholds:
        return self._thresholds

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _notify(self, specific_signal: Signal | None = None) -> None:
        self._dirty = True
        if specific_signal is not None:
            specific_signal.emit()
        self.changed.emit()

    def touch(self) -> None:
        """General SYNCHRONOUS notify - for changes not tied to a single
        entity (e.g. renaming the project, changing thresholds). Safe to be
        synchronous since it's called from plain button-click handlers, not
        from a table's setData() (for that case use touch_servers/
        touch_storages/touch_vms, which are deliberately deferred)."""
        self._notify()

    def touch_servers(self) -> None:
        """Deferred notify (QTimer) for inline edits on the Servers table -
        see the note in the touch_* methods below on why the delay is needed."""
        QTimer.singleShot(0, lambda: self._notify(self.servers_changed))

    def touch_storages(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.storages_changed))

    def touch_vms(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.vms_changed))

    # ------------------------------------------------------------------
    # Project: new / save / load
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        self._project = ClusterProject()
        self._current_path = None
        self._dirty = False
        self.changed.emit()
        self.servers_changed.emit()
        self.storages_changed.emit()
        self.vms_changed.emit()
        self.network_changed.emit()

    def save_project(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self._current_path
        if target is None:
            raise ValueError("Nije zadan path za spremanje projekta.")

        project_repository.save_project(self._project, target)
        self._current_path = target
        self._dirty = False
        return target

    def load_project(self, path: str | Path) -> None:
        self._project = project_repository.load_project(path)
        self._current_path = Path(path)
        self._dirty = False
        self.changed.emit()
        self.servers_changed.emit()
        self.storages_changed.emit()
        self.vms_changed.emit()
        self.network_changed.emit()

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------

    def add_server(self, server: Server) -> None:
        self._project.servers.append(server)
        self._notify(self.servers_changed)

    def add_servers(self, servers: list[Server]) -> None:
        """Batch add - a single changed signal for the whole group."""
        self._project.servers.extend(servers)
        self._notify(self.servers_changed)

    def update_server(self, index: int, server: Server) -> None:
        self._project.servers[index] = server
        self._notify(self.servers_changed)

    def remove_servers(self, servers: list[Server]) -> None:
        removed = set(id(s) for s in servers)
        self._project.servers = [s for s in self._project.servers if id(s) not in removed]
        self._notify(self.servers_changed)

    def clear_servers(self) -> None:
        self._project.servers = []
        self._notify(self.servers_changed)

    def server_count(self) -> int:
        return len(self._project.servers)

    def import_servers_csv(self, path: str | Path) -> int:
        new_servers = csv_io.import_servers(path)
        self._project.servers.extend(new_servers)
        self._notify(self.servers_changed)
        return len(new_servers)

    def export_servers_csv(self, path: str | Path) -> None:
        csv_io.export_servers(path, self._project.servers)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def add_storage(self, storage: Storage) -> None:
        self._project.storages.append(storage)
        self._notify(self.storages_changed)

    def update_storage(self, index: int, storage: Storage) -> None:
        self._project.storages[index] = storage
        self._notify(self.storages_changed)

    def remove_storages(self, storages: list[Storage]) -> None:
        removed = set(id(s) for s in storages)
        self._project.storages = [s for s in self._project.storages if id(s) not in removed]
        self._notify(self.storages_changed)

    def clear_storages(self) -> None:
        self._project.storages = []
        self._notify(self.storages_changed)

    def import_storages_csv(self, path: str | Path) -> int:
        new_storages = csv_io.import_storages(path)
        self._project.storages.extend(new_storages)
        self._notify(self.storages_changed)
        return len(new_storages)

    def export_storages_csv(self, path: str | Path) -> None:
        csv_io.export_storages(path, self._project.storages)

    # ------------------------------------------------------------------
    # Virtual machines
    # ------------------------------------------------------------------

    def add_vm(self, vm: VirtualMachine) -> None:
        self._project.vms.append(vm)
        self._notify(self.vms_changed)

    def add_vms(self, vms: list[VirtualMachine]) -> None:
        """Batch add - a single changed signal for the whole group (used by
        the Smart Import wizard and CSV import)."""
        self._project.vms.extend(vms)
        self._notify(self.vms_changed)

    def update_vm(self, index: int, vm: VirtualMachine) -> None:
        self._project.vms[index] = vm
        self._notify(self.vms_changed)

    def remove_vms(self, vms: list[VirtualMachine]) -> None:
        removed = set(id(v) for v in vms)
        self._project.vms = [v for v in self._project.vms if id(v) not in removed]
        self._notify(self.vms_changed)

    def clear_vms(self) -> None:
        self._project.vms = []
        self._notify(self.vms_changed)

    def import_vms_csv(self, path: str | Path) -> int:
        new_vms = csv_io.import_vms(path)
        self._project.vms.extend(new_vms)
        self._notify(self.vms_changed)
        return len(new_vms)

    def export_vms_csv(self, path: str | Path) -> None:
        csv_io.export_vms(path, self._project.vms)

    # ------------------------------------------------------------------
    # Network switches
    # ------------------------------------------------------------------

    def add_switch(self, switch: NetworkSwitch) -> None:
        self._project.switches.append(switch)
        self._notify(self.network_changed)

    def update_switch(self, index: int, switch: NetworkSwitch) -> None:
        self._project.switches[index] = switch
        self._notify(self.network_changed)

    def remove_switches(self, switches: list[NetworkSwitch]) -> None:
        removed_uids = {s.uid for s in switches}
        self._project.switches = [s for s in self._project.switches if s.uid not in removed_uids]
        # Connections that referenced the deleted switch become orphan
        # records - we don't auto-delete them (see NetworkConnection docstring).
        self._notify(self.network_changed)

    def clear_switches(self) -> None:
        self._project.switches = []
        self._notify(self.network_changed)

    def import_switches_csv(self, path: str | Path) -> int:
        new_switches = csv_io.import_switches(path)
        self._project.switches.extend(new_switches)
        self._notify(self.network_changed)
        return len(new_switches)

    def export_switches_csv(self, path: str | Path) -> None:
        csv_io.export_switches(path, self._project.switches)

    # ------------------------------------------------------------------
    # Network connections
    # ------------------------------------------------------------------

    def add_connection(self, connection: NetworkConnection) -> None:
        self._project.connections.append(connection)
        self._notify(self.network_changed)

    def update_connection(self, index: int, connection: NetworkConnection) -> None:
        self._project.connections[index] = connection
        self._notify(self.network_changed)

    def remove_connections(self, connections: list[NetworkConnection]) -> None:
        removed = set(id(c) for c in connections)
        self._project.connections = [
            c for c in self._project.connections if id(c) not in removed
        ]
        self._notify(self.network_changed)

    def clear_connections(self) -> None:
        self._project.connections = []
        self._notify(self.network_changed)

    def import_connections_csv(self, path: str | Path) -> tuple[int, int]:
        """Returns (number imported, number skipped due to unknown server/switch name)."""
        new_connections, skipped = csv_io.import_connections(
            path, self._project.servers, self._project.switches
        )
        self._project.connections.extend(new_connections)
        self._notify(self.network_changed)
        return len(new_connections), skipped

    def export_connections_csv(self, path: str | Path) -> None:
        csv_io.export_connections(
            path, self._project.connections, self._project.servers, self._project.switches
        )
