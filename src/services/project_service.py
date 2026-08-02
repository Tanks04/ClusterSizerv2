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
    """Centralna servisna klasa za rad s aktivnim projektom.

    `changed` je opći signal (za Dashboard/Summary/Reports/naslov prozora -
    stranice kojima treba znati o BILO kojoj promjeni). servers_changed /
    storages_changed / vms_changed / network_changed su uži signali - svaka
    CRUD tablica se pretplati SAMO na svoj, da se ne radi beginResetModel()
    na tablicama čiji se podaci uopće nisu promijenili. Ovo nije samo
    performansa: veliki broj nepotrebnih model-reseta odjednom (npr. dodaš
    jedan Storage i sve od Servera do Networka se resetira) povećava šansu
    da se pogodi timing-osjetljiv Qt/PySide bug (vidi ROADMAP - crash na
    Windowsima vezan za QHeaderView.ResizeToContents).
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
        """Generalni SINKRONI notify - za promjene koje nisu vezane za jedan
        entitet (npr. rename projekta, promjena thresholda). Sigurno je
        sinkrono jer se zove iz običnih button-click handlera, ne iz
        tabličnog setData() (za taj slučaj koristi touch_servers/
        touch_storages/touch_vms, koji su namjerno odgođeni)."""
        self._notify()

    def touch_servers(self) -> None:
        """Odgođeni notify (QTimer) za inline edit na Servers tablici - vidi
        napomenu u touch_* metodama niže o zašto je odgoda nužna."""
        QTimer.singleShot(0, lambda: self._notify(self.servers_changed))

    def touch_storages(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.storages_changed))

    def touch_vms(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.vms_changed))

    # ------------------------------------------------------------------
    # Projekt: new / save / load
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
        """Batch dodavanje - jedan changed signal za cijelu grupu."""
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
        # Veze koje su visile na obrisanom switchu postaju orphan zapisi -
        # ne brišemo ih automatski (vidi NetworkConnection docstring).
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
        """Vraća (broj uvezenih, broj preskočenih zbog nepoznatog server/switch imena)."""
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
