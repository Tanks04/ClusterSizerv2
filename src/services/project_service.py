import copy
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

MAX_UNDO_DEPTH = 50


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

    Undo/redo: a snapshot (deep copy) of the whole project is pushed onto
    an undo stack before every structural mutation (add/update/remove/
    clear/import). This is deliberately snapshot-based rather than a
    command pattern with per-operation inverses - projects are small
    (tens/hundreds of rows, not thousands), so deep-copying the whole
    thing is cheap, and it means every single mutating method only needs
    ONE extra line instead of a hand-written undo for each. Scope:
    inline cell edits (double-click a table cell and type a new number)
    are NOT on the undo stack - those are low-risk (easy to just retype),
    and covering them would mean snapshotting on every keystroke's commit.
    Undo covers the destructive/structural actions where it actually
    matters: Add, Delete, Duplicate, Import, Clear All.
    """

    changed = Signal()

    servers_changed = Signal()
    storages_changed = Signal()
    vms_changed = Signal()
    network_changed = Signal()  # switches + connections together

    undo_state_changed = Signal()  # for enabling/disabling Undo/Redo menu items

    def __init__(self) -> None:
        super().__init__()
        self._project = ClusterProject()
        self._thresholds = Thresholds()
        self._current_path: Path | None = None
        self._dirty = False
        self._undo_stack: list[ClusterProject] = []
        self._redo_stack: list[ClusterProject] = []

    # ------------------------------------------------------------------
    # Basic state
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
        see the note in the touch_* methods below on why the delay is needed.
        NOT on the undo stack - see the ProjectService docstring."""
        QTimer.singleShot(0, lambda: self._notify(self.servers_changed))

    def touch_storages(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.storages_changed))

    def touch_vms(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.vms_changed))

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _push_undo_snapshot(self) -> None:
        self._undo_stack.append(copy.deepcopy(self._project))
        if len(self._undo_stack) > MAX_UNDO_DEPTH:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self.undo_state_changed.emit()

    def _clear_undo_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.undo_state_changed.emit()

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(copy.deepcopy(self._project))
        self._project = self._undo_stack.pop()
        self._dirty = True
        self.undo_state_changed.emit()
        self._emit_everything_changed()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(copy.deepcopy(self._project))
        self._project = self._redo_stack.pop()
        self._dirty = True
        self.undo_state_changed.emit()
        self._emit_everything_changed()

    def _emit_everything_changed(self) -> None:
        self.changed.emit()
        self.servers_changed.emit()
        self.storages_changed.emit()
        self.vms_changed.emit()
        self.network_changed.emit()

    # ------------------------------------------------------------------
    # Project: new / save / load
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        self._project = ClusterProject()
        self._current_path = None
        self._dirty = False
        self._clear_undo_history()
        self._emit_everything_changed()

    def save_project(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self._current_path
        if target is None:
            raise ValueError("No path given to save the project to.")

        project_repository.save_project(self._project, target)
        self._current_path = target
        self._dirty = False
        return target

    def save_copy_as(self, path: str | Path) -> Path:
        """Writes the current project to `path` WITHOUT making it the
        active file - a branch/snapshot for scenario comparison, not a
        'save as and keep editing here' operation. You keep working on the
        original; load the copy later on the Compare page as Scenario B."""
        target = Path(path)
        project_repository.save_project(self._project, target)
        return target

    def load_project(self, path: str | Path) -> None:
        self._project = project_repository.load_project(path)
        self._current_path = Path(path)
        self._dirty = False
        self._clear_undo_history()
        self._emit_everything_changed()

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------

    def add_server(self, server: Server) -> None:
        self._push_undo_snapshot()
        self._project.servers.append(server)
        self._notify(self.servers_changed)

    def add_servers(self, servers: list[Server]) -> None:
        """Batch add - a single changed signal for the whole group."""
        self._push_undo_snapshot()
        self._project.servers.extend(servers)
        self._notify(self.servers_changed)

    def set_all_servers_hyperthreading(self, enabled: bool) -> None:
        """Bulk-sets hyperthreading_enabled on every server at once - one
        undo snapshot for the whole action, not one per server, so a
        single Ctrl+Z reverts it all."""
        self._push_undo_snapshot()
        for server in self._project.servers:
            server.hyperthreading_enabled = enabled
        self._notify(self.servers_changed)

    def update_server(self, index: int, server: Server) -> None:
        self._push_undo_snapshot()
        self._project.servers[index] = server
        self._notify(self.servers_changed)

    def remove_servers(self, servers: list[Server]) -> None:
        self._push_undo_snapshot()
        removed = set(id(s) for s in servers)
        self._project.servers = [s for s in self._project.servers if id(s) not in removed]
        self._notify(self.servers_changed)

    def clear_servers(self) -> None:
        self._push_undo_snapshot()
        self._project.servers = []
        self._notify(self.servers_changed)

    def server_count(self) -> int:
        return len(self._project.servers)

    def import_servers_csv(self, path: str | Path) -> int:
        new_servers = csv_io.import_servers(path)
        self._push_undo_snapshot()
        self._project.servers.extend(new_servers)
        self._notify(self.servers_changed)
        return len(new_servers)

    def export_servers_csv(self, path: str | Path) -> None:
        csv_io.export_servers(path, self._project.servers)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def add_storage(self, storage: Storage) -> None:
        self._push_undo_snapshot()
        self._project.storages.append(storage)
        self._notify(self.storages_changed)

    def update_storage(self, index: int, storage: Storage) -> None:
        self._push_undo_snapshot()
        self._project.storages[index] = storage
        self._notify(self.storages_changed)

    def remove_storages(self, storages: list[Storage]) -> None:
        self._push_undo_snapshot()
        removed = set(id(s) for s in storages)
        self._project.storages = [s for s in self._project.storages if id(s) not in removed]
        self._notify(self.storages_changed)

    def clear_storages(self) -> None:
        self._push_undo_snapshot()
        self._project.storages = []
        self._notify(self.storages_changed)

    def import_storages_csv(self, path: str | Path) -> int:
        new_storages = csv_io.import_storages(path)
        self._push_undo_snapshot()
        self._project.storages.extend(new_storages)
        self._notify(self.storages_changed)
        return len(new_storages)

    def export_storages_csv(self, path: str | Path) -> None:
        csv_io.export_storages(path, self._project.storages)

    # ------------------------------------------------------------------
    # Virtual machines
    # ------------------------------------------------------------------

    def add_vm(self, vm: VirtualMachine) -> None:
        self._push_undo_snapshot()
        self._project.vms.append(vm)
        self._notify(self.vms_changed)

    def add_vms(self, vms: list[VirtualMachine]) -> None:
        """Batch add - a single changed signal for the whole group (used by
        the Smart Import wizard and CSV import)."""
        self._push_undo_snapshot()
        self._project.vms.extend(vms)
        self._notify(self.vms_changed)

    def update_vm(self, index: int, vm: VirtualMachine) -> None:
        self._push_undo_snapshot()
        self._project.vms[index] = vm
        self._notify(self.vms_changed)

    def remove_vms(self, vms: list[VirtualMachine]) -> None:
        self._push_undo_snapshot()
        removed = set(id(v) for v in vms)
        self._project.vms = [v for v in self._project.vms if id(v) not in removed]
        self._notify(self.vms_changed)

    def clear_vms(self) -> None:
        self._push_undo_snapshot()
        self._project.vms = []
        self._notify(self.vms_changed)

    def import_vms_csv(self, path: str | Path) -> int:
        new_vms = csv_io.import_vms(path)
        self._push_undo_snapshot()
        self._project.vms.extend(new_vms)
        self._notify(self.vms_changed)
        return len(new_vms)

    def export_vms_csv(self, path: str | Path) -> None:
        csv_io.export_vms(path, self._project.vms)

    # ------------------------------------------------------------------
    # Network switches
    # ------------------------------------------------------------------

    def add_switch(self, switch: NetworkSwitch) -> None:
        self._push_undo_snapshot()
        self._project.switches.append(switch)
        self._notify(self.network_changed)

    def update_switch(self, index: int, switch: NetworkSwitch) -> None:
        self._push_undo_snapshot()
        self._project.switches[index] = switch
        self._notify(self.network_changed)

    def remove_switches(self, switches: list[NetworkSwitch]) -> None:
        self._push_undo_snapshot()
        removed_uids = {s.uid for s in switches}
        self._project.switches = [s for s in self._project.switches if s.uid not in removed_uids]
        # Connections that referenced the deleted switch become orphan
        # records - we don't auto-delete them (see NetworkConnection docstring).
        self._notify(self.network_changed)

    def clear_switches(self) -> None:
        self._push_undo_snapshot()
        self._project.switches = []
        self._notify(self.network_changed)

    def import_switches_csv(self, path: str | Path) -> int:
        new_switches = csv_io.import_switches(path)
        self._push_undo_snapshot()
        self._project.switches.extend(new_switches)
        self._notify(self.network_changed)
        return len(new_switches)

    def export_switches_csv(self, path: str | Path) -> None:
        csv_io.export_switches(path, self._project.switches)

    # ------------------------------------------------------------------
    # Network connections
    # ------------------------------------------------------------------

    def add_connection(self, connection: NetworkConnection) -> None:
        self._push_undo_snapshot()
        self._project.connections.append(connection)
        self._notify(self.network_changed)

    def update_connection(self, index: int, connection: NetworkConnection) -> None:
        self._push_undo_snapshot()
        self._project.connections[index] = connection
        self._notify(self.network_changed)

    def remove_connections(self, connections: list[NetworkConnection]) -> None:
        self._push_undo_snapshot()
        removed = set(id(c) for c in connections)
        self._project.connections = [
            c for c in self._project.connections if id(c) not in removed
        ]
        self._notify(self.network_changed)

    def clear_connections(self) -> None:
        self._push_undo_snapshot()
        self._project.connections = []
        self._notify(self.network_changed)

    def import_connections_csv(self, path: str | Path) -> tuple[int, int]:
        """Returns (number imported, number skipped due to unknown server/switch/storage name)."""
        new_connections, skipped = csv_io.import_connections(
            path, self._project.servers, self._project.switches, self._project.storages
        )
        self._push_undo_snapshot()
        self._project.connections.extend(new_connections)
        self._notify(self.network_changed)
        return len(new_connections), skipped

    def export_connections_csv(self, path: str | Path) -> None:
        csv_io.export_connections(
            path, self._project.connections, self._project.servers,
            self._project.switches, self._project.storages,
        )
