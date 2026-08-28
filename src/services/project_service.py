import copy
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.vlan import Vlan
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.persistence import csv_io, project_repository

MAX_UNDO_DEPTH = 50


class ProjectService(QObject):
    """Central service class for working with the active project.

    `changed` is the general signal (for Summary/Reports/window
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
    backup_changed = Signal()
    pricing_changed = Signal()

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

    def touch_backup_destinations(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.backup_changed))

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

        project_repository.save_project(self._project, target, self._thresholds)
        self._current_path = target
        self._dirty = False
        return target

    def save_copy_as(self, path: str | Path) -> Path:
        """Writes the current project to `path` WITHOUT making it the
        active file - a branch/snapshot for scenario comparison, not a
        'save as and keep editing here' operation. You keep working on the
        original; load the copy later on the Compare page as Scenario B."""
        target = Path(path)
        project_repository.save_project(self._project, target, self._thresholds)
        return target

    def load_project(self, path: str | Path) -> None:
        loaded = project_repository.load_project(path)
        self._project = loaded.project
        self._thresholds = loaded.thresholds
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

    def add_servers_and_storages(self, servers: list[Server], storages: list[Storage]) -> None:
        """Add both at once as ONE undoable action (one snapshot, not two)
        - used by Cluster Preparation's "Add Recommended Cluster" buttons,
        so a single Ctrl+Z removes the whole recommendation, servers and
        storage together, not just half of it."""
        self._push_undo_snapshot()
        self._project.servers.extend(servers)
        self._project.storages.extend(storages)
        self.servers_changed.emit()
        self.storages_changed.emit()
        self._notify()

    def add_servers_and_vms(
        self, servers: list[Server], vms: list[VirtualMachine],
        switches: list[NetworkSwitch] | None = None,
    ) -> None:
        """Same idea as add_servers_and_storages, for RVTools import -
        one file can produce hosts, VMs, and (optionally) switches, one
        undo step for the whole import."""
        self._push_undo_snapshot()
        self._project.servers.extend(servers)
        self._project.vms.extend(vms)
        if switches:
            self._project.switches.extend(switches)
        self.servers_changed.emit()
        self.vms_changed.emit()
        if switches:
            self.network_changed.emit()
        self._notify()

    def replace_servers_and_storages_at_site(
        self, site: str, servers: list[Server], storages: list[Storage]
    ) -> None:
        """Same as add_servers_and_storages, but first removes any
        EXISTING servers/storages at `site` - one undo step for the
        whole swap. Used when applying a Cluster Preparation
        recommendation on top of a site that already has servers/storage
        from before, and the user chose "Replace" over "Add"."""
        self._push_undo_snapshot()
        self._project.servers = [s for s in self._project.servers if s.site != site]
        self._project.storages = [s for s in self._project.storages if s.site != site]
        self._project.servers.extend(servers)
        self._project.storages.extend(storages)
        self.servers_changed.emit()
        self.storages_changed.emit()
        self._notify()

    def set_all_servers_hyperthreading(self, enabled: bool) -> None:
        """Bulk-sets hyperthreading_enabled on every server at once - one
        undo snapshot for the whole action, not one per server, so a
        single Ctrl+Z reverts it all."""
        self._push_undo_snapshot()
        for server in self._project.servers:
            server.hyperthreading_enabled = enabled
        self._notify(self.servers_changed)

    def set_primary_deployment_model(self, model: str) -> None:
        self._push_undo_snapshot()
        self._project.primary_deployment_model = model
        self._notify()

    def set_dr_deployment_model(self, model: str) -> None:
        self._push_undo_snapshot()
        self._project.dr_deployment_model = model
        self._notify()

    def set_primary_rack_capacity_u(self, capacity: int) -> None:
        self._push_undo_snapshot()
        self._project.primary_rack_capacity_u = capacity
        self._notify()

    def set_dr_rack_capacity_u(self, capacity: int) -> None:
        self._push_undo_snapshot()
        self._project.dr_rack_capacity_u = capacity
        self._notify()

    def set_enabled_for_servers(self, servers: list[Server], enabled: bool) -> None:
        """Toggles Server.enabled for a selection - excludes/includes them
        from all capacity math without deleting the server's whole
        configuration. Quick way to simulate "this host is down"
        (maintenance, a real failure) and see the effect on
        oversubscription/N+1 immediately. One undo snapshot for the whole
        selection."""
        if not servers:
            return
        self._push_undo_snapshot()
        for server in servers:
            server.enabled = enabled
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

    def add_storages(self, storages: list[Storage]) -> None:
        """Batch add - a single undo snapshot and changed signal for the
        whole group (mirrors add_servers/add_vms)."""
        self._push_undo_snapshot()
        self._project.storages.extend(storages)
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

    # ------------------------------------------------------------------
    # Backup Destinations
    # ------------------------------------------------------------------

    def add_backup_destination(self, destination: BackupDestination) -> None:
        self._push_undo_snapshot()
        self._project.backup_destinations.append(destination)
        self._notify(self.backup_changed)

    def add_backup_destinations(self, destinations: list[BackupDestination]) -> None:
        self._push_undo_snapshot()
        self._project.backup_destinations.extend(destinations)
        self._notify(self.backup_changed)

    def update_backup_destination(self, index: int, destination: BackupDestination) -> None:
        self._push_undo_snapshot()
        self._project.backup_destinations[index] = destination
        self._notify(self.backup_changed)

    def remove_backup_destinations(self, destinations: list[BackupDestination]) -> None:
        self._push_undo_snapshot()
        removed = set(id(d) for d in destinations)
        self._project.backup_destinations = [
            d for d in self._project.backup_destinations if id(d) not in removed
        ]
        self._notify(self.backup_changed)

    def clear_backup_destinations(self) -> None:
        self._push_undo_snapshot()
        self._project.backup_destinations = []
        self._notify(self.backup_changed)

    def import_backup_destinations_csv(self, path: str | Path) -> int:
        new_destinations = csv_io.import_backup_destinations(path)
        self._push_undo_snapshot()
        self._project.backup_destinations.extend(new_destinations)
        self._notify(self.backup_changed)
        return len(new_destinations)

    def export_backup_destinations_csv(self, path: str | Path) -> None:
        csv_io.export_backup_destinations(path, self._project.backup_destinations)

    # ------------------------------------------------------------------
    # Maintenance Items (licenses, warranties, subscriptions, support)
    # ------------------------------------------------------------------

    def add_maintenance_item(self, item: MaintenanceItem) -> None:
        self._push_undo_snapshot()
        self._project.maintenance_items.append(item)
        self._notify(self.pricing_changed)

    def update_maintenance_item(self, index: int, item: MaintenanceItem) -> None:
        self._push_undo_snapshot()
        self._project.maintenance_items[index] = item
        self._notify(self.pricing_changed)

    def remove_maintenance_items(self, items: list[MaintenanceItem]) -> None:
        self._push_undo_snapshot()
        removed = set(id(i) for i in items)
        self._project.maintenance_items = [
            i for i in self._project.maintenance_items if id(i) not in removed
        ]
        self._notify(self.pricing_changed)

    def clear_maintenance_items(self) -> None:
        self._push_undo_snapshot()
        self._project.maintenance_items = []
        self._notify(self.pricing_changed)

    def touch_pricing(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.pricing_changed))

    def import_maintenance_items_csv(self, path: str | Path) -> int:
        new_items = csv_io.import_maintenance_items(path)
        self._push_undo_snapshot()
        self._project.maintenance_items.extend(new_items)
        self._notify(self.pricing_changed)
        return len(new_items)

    def export_maintenance_items_csv(self, path: str | Path) -> None:
        csv_io.export_maintenance_items(path, self._project.maintenance_items)

    # ------------------------------------------------------------------
    # VLANs
    # ------------------------------------------------------------------

    def add_vlan(self, vlan: Vlan) -> None:
        self._push_undo_snapshot()
        self._project.vlans.append(vlan)
        self._notify(self.network_changed)

    def update_vlan(self, index: int, vlan: Vlan) -> None:
        self._push_undo_snapshot()
        self._project.vlans[index] = vlan
        self._notify(self.network_changed)

    def remove_vlans(self, vlans: list[Vlan]) -> None:
        """Also clears vlan_uid on any VM that referenced one of the
        removed VLANs - a VM shouldn't silently keep pointing at a
        deleted VLAN's uid."""
        self._push_undo_snapshot()
        removed_uids = {v.uid for v in vlans}
        self._project.vlans = [v for v in self._project.vlans if v.uid not in removed_uids]
        for vm in self._project.vms:
            if vm.vlan_uid in removed_uids:
                vm.vlan_uid = ""
        self.network_changed.emit()
        self.vms_changed.emit()
        self._notify()

    def clear_vlans(self) -> None:
        self._push_undo_snapshot()
        self._project.vlans = []
        for vm in self._project.vms:
            vm.vlan_uid = ""
        self.network_changed.emit()
        self.vms_changed.emit()
        self._notify()

    def import_vlans_csv(self, path: str | Path) -> int:
        new_vlans = csv_io.import_vlans(path)
        self._push_undo_snapshot()
        self._project.vlans.extend(new_vlans)
        self._notify(self.network_changed)
        return len(new_vlans)

    def export_vlans_csv(self, path: str | Path) -> None:
        csv_io.export_vlans(path, self._project.vlans)

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

    def set_all_vms_workload_tier(self, tier: str) -> None:
        """Bulk-sets workload_tier on every VM at once - one undo snapshot
        for the whole action, not one per VM, so a single Ctrl+Z reverts
        it all. A quick way to size a whole cluster without editing VMs
        one by one first."""
        self._push_undo_snapshot()
        for vm in self._project.vms:
            vm.workload_tier = tier
        self._notify(self.vms_changed)

    def set_all_vms_dr_protected(self, protected: bool) -> None:
        """Bulk-sets dr_protected on every VM at once - one undo snapshot
        for the whole action. Turning it ON also defaults each VM's DR
        footprint to match its primary footprint (vcpu/ram/disk) unless
        it already had DR values set; turning it OFF just clears the flag,
        leaving the footprint numbers in place in case it's turned back on."""
        self._push_undo_snapshot()
        for vm in self._project.vms:
            self._apply_dr_protected(vm, protected)
        self._notify(self.vms_changed)

    def set_dr_protected_for_vms(self, vms: list[VirtualMachine], protected: bool) -> None:
        """Same as set_all_vms_dr_protected, but scoped to a specific
        selection (e.g. from a table's right-click menu or "Apply to
        Selected") - one undo snapshot for the whole selection, not one
        per VM. The typical workflow this exists for: load 45 VMs, select
        only the 12 that should actually go to DR, mark just those."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            self._apply_dr_protected(vm, protected)
        self._notify(self.vms_changed)

    @staticmethod
    def _apply_dr_protected(vm: VirtualMachine, protected: bool) -> None:
        vm.dr_protected = protected
        if protected and vm.dr_vcpu == 0 and vm.dr_ram_gb == 0 and vm.dr_disk_gb == 0:
            vm.dr_vcpu = vm.vcpu
            vm.dr_ram_gb = vm.ram_gb
            vm.dr_disk_gb = vm.disk_gb

    def set_workload_tier_for_vms(self, vms: list[VirtualMachine], tier: str) -> None:
        """Same as set_all_vms_workload_tier, but scoped to a selection -
        one undo snapshot for the whole selection."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            vm.workload_tier = tier
        self._notify(self.vms_changed)

    def set_site_for_vms(self, vms: list[VirtualMachine], site: str) -> None:
        """Moves the given VMs to a different site (Primary/DR) - a
        DIFFERENT concept from dr_protected (which flags a VM as
        replicated to DR while it keeps living on its current site).
        This actually relocates where the VM "lives". One undo snapshot
        for the whole selection."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            vm.site = site
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

    def add_switches(self, switches: list[NetworkSwitch]) -> None:
        """Batch add - a single undo snapshot and changed signal for the
        whole group (mirrors add_servers/add_vms)."""
        self._push_undo_snapshot()
        self._project.switches.extend(switches)
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

    def add_connections(self, connections: list[NetworkConnection]) -> None:
        """Batch add - a single undo snapshot and changed signal for the
        whole group (mirrors add_servers/add_vms)."""
        self._push_undo_snapshot()
        self._project.connections.extend(connections)
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
