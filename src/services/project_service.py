import copy
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from src.calculations.thresholds import Thresholds
from src.models.backup_destination import BackupDestination
from src.models.cluster import Cluster, find_or_create_clusters_by_name
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.maintenance_item import MaintenanceItem
from src.models.network_connection import NetworkConnection
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan
from src.persistence import csv_io, project_repository

MAX_UNDO_DEPTH = 50


class ProjectService(QObject):
    """Central service class for working with the active project.

    `changed` is the general signal (for Summary/Reports/window
    title - pages that need to know about ANY change). servers_changed /
    storages_changed / vms_changed / network_changed / clusters_changed /
    backup_changed / pricing_changed are narrower signals - each CRUD
    table subscribes to ONLY its own, so it doesn't run
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
    clusters_changed = Signal()
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
        self.clusters_changed.emit()
        self.backup_changed.emit()
        self.pricing_changed.emit()

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
        switches: list[NetworkSwitch] | None = None, replace: bool = False,
        new_clusters: list[Cluster] | None = None,
    ) -> None:
        """Same idea as add_servers_and_storages, for RVTools import -
        one file can produce hosts, VMs, and (optionally) switches, one
        undo step for the whole import. replace=True clears all three
        existing lists first - cascades to FailoverAssignment records
        the same way clear_vms() does, since an assignment pointing at
        a VM that no longer exists would be orphaned. new_clusters are
        appended (never replaced/cleared, even when replace=True) -
        these come from find_or_create_clusters_by_name() converting
        each server's cluster_name into a real Cluster assignment, in
        the same undo step as the servers/VMs themselves."""
        self._push_undo_snapshot()
        if replace:
            self._project.servers = list(servers)
            self._project.vms = list(vms)
            self._project.failover_assignments = []
            if switches:
                self._project.switches = list(switches)
        else:
            self._project.servers.extend(servers)
            self._project.vms.extend(vms)
            if switches:
                self._project.switches.extend(switches)
        if new_clusters:
            self._project.clusters.extend(new_clusters)
        self.servers_changed.emit()
        self.vms_changed.emit()
        if switches:
            self.network_changed.emit()
        if new_clusters:
            self.clusters_changed.emit()
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

    def set_deployment_model(self, site: str, model: str) -> None:
        self._push_undo_snapshot()
        self._project.set_deployment_model(site, model)
        self._notify()

    def set_rack_capacity_u(self, site: str, capacity: int) -> None:
        self._push_undo_snapshot()
        self._project.set_rack_capacity_u(site, capacity)
        self._notify()

    def add_site(self, name: str) -> None:
        self._push_undo_snapshot()
        self._project.add_site(name)
        self._notify()

    def site_in_use(self, name: str) -> bool:
        """Whether any entity currently references this site - used to
        decide whether remove_site() can proceed safely or should be
        refused, since (unlike VLAN) a Server/VM/etc. can't have an
        empty/unset site the way a VM's optional vlan_uid can."""
        return (
            any(s.site == name for s in self._project.servers)
            or any(s.site == name for s in self._project.storages)
            or any(v.site == name for v in self._project.vms)
            or any(s.site == name for s in self._project.switches)
            or any(d.site == name for d in self._project.backup_destinations)
            or any(v.site == name for v in self._project.vlans)
            or any(a.target_site == name for a in self._project.failover_assignments)
        )

    def remove_site(self, name: str) -> None:
        """Raises ValueError if name is Primary. Refuses (RuntimeError)
        if any entity still references this site - the caller should
        check site_in_use() first and prompt the user to reassign/
        delete those entities, rather than this silently orphaning them
        or silently deleting them. Both checks happen BEFORE the undo
        snapshot is pushed, so a refused removal doesn't leave a
        no-op entry in the undo stack."""
        if name == PRIMARY:
            raise ValueError("Cannot remove the Primary site")
        if self.site_in_use(name):
            raise RuntimeError(
                f'"{name}" is still in use by at least one Server, Storage, VM, '
                "Switch, Backup Destination, VLAN, or Failover Assignment - "
                "reassign or delete those first."
            )
        self._push_undo_snapshot()
        self._project.remove_site(name)
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

    def set_powered_on_for_vms(self, vms: list[VirtualMachine], powered_on: bool) -> None:
        """Same idea as set_enabled_for_servers, for VM.powered_on -
        already excluded from every vCPU/RAM/disk demand calculation
        throughout the app; this is the bulk right-click toggle for it.
        One undo snapshot for the whole selection."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            vm.powered_on = powered_on
        self._notify(self.vms_changed)

    def update_server(self, index: int, server: Server) -> None:
        self._push_undo_snapshot()
        self._project.servers[index] = server
        self._notify(self.servers_changed)

    def remove_servers(self, servers: list[Server]) -> None:
        self._push_undo_snapshot()
        removed_uids = {s.uid for s in servers}
        self._project.servers = [s for s in self._project.servers if s.uid not in removed_uids]
        self._notify(self.servers_changed)

    def clear_servers(self) -> None:
        self._push_undo_snapshot()
        self._project.servers = []
        self._notify(self.servers_changed)

    def server_count(self) -> int:
        return len(self._project.servers)

    def import_servers_csv(self, path: str | Path, replace: bool = False) -> int:
        new_servers = csv_io.import_servers(path)
        new_clusters = find_or_create_clusters_by_name(self._project.clusters, new_servers)
        self._push_undo_snapshot()
        self._project.servers = new_servers if replace else self._project.servers + new_servers
        if new_clusters:
            self._project.clusters.extend(new_clusters)
        self._notify(self.servers_changed)
        if new_clusters:
            self.clusters_changed.emit()
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

    def add_servers_to_storage_zoning(self, storage_uid: str, server_uids: list[str]) -> None:
        """Adds the given servers to a Storage's server_uids (array-
        wide host zoning) - additive, doesn't clear whatever's already
        zoned there. One undo step, regardless of how many servers.
        Used by all three Servers-tab bulk-assign paths (Selected/All/
        By Cluster) - the cluster-expansion into member server uids
        happens in the caller, this just appends without duplicates."""
        storage = next((s for s in self._project.storages if s.uid == storage_uid), None)
        if storage is None:
            return
        self._push_undo_snapshot()
        for uid in server_uids:
            if uid not in storage.server_uids:
                storage.server_uids.append(uid)
        self._notify(self.storages_changed)

    def remove_storages(self, storages: list[Storage]) -> None:
        self._push_undo_snapshot()
        removed_uids = {s.uid for s in storages}
        self._project.storages = [s for s in self._project.storages if s.uid not in removed_uids]
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
        removed_uids = {d.uid for d in destinations}
        self._project.backup_destinations = [
            d for d in self._project.backup_destinations if d.uid not in removed_uids
        ]
        self._notify(self.backup_changed)

    def clear_backup_destinations(self) -> None:
        self._push_undo_snapshot()
        self._project.backup_destinations = []
        self._notify(self.backup_changed)

    def import_backup_destinations_csv(self, path: str | Path, replace: bool = False) -> int:
        new_destinations = csv_io.import_backup_destinations(path)
        self._push_undo_snapshot()
        self._project.backup_destinations = new_destinations if replace else self._project.backup_destinations + new_destinations
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
        removed_uids = {i.uid for i in items}
        self._project.maintenance_items = [
            i for i in self._project.maintenance_items if i.uid not in removed_uids
        ]
        self._notify(self.pricing_changed)

    def clear_maintenance_items(self) -> None:
        self._push_undo_snapshot()
        self._project.maintenance_items = []
        self._notify(self.pricing_changed)

    def touch_pricing(self) -> None:
        QTimer.singleShot(0, lambda: self._notify(self.pricing_changed))

    def import_maintenance_items_csv(self, path: str | Path, replace: bool = False) -> int:
        new_items = csv_io.import_maintenance_items(path)
        self._push_undo_snapshot()
        self._project.maintenance_items = new_items if replace else self._project.maintenance_items + new_items
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

    def add_cluster(self, cluster: Cluster) -> None:
        self._push_undo_snapshot()
        self._project.clusters.append(cluster)
        self._notify(self.clusters_changed)

    def update_cluster(self, index: int, cluster: Cluster) -> None:
        self._push_undo_snapshot()
        self._project.clusters[index] = cluster
        self._notify(self.clusters_changed)

    def remove_clusters(self, clusters: list[Cluster]) -> None:
        """Also clears cluster_uid on any Server or VM that referenced
        one of the removed clusters - neither should silently keep
        pointing at a deleted cluster's uid."""
        self._push_undo_snapshot()
        removed_uids = {c.uid for c in clusters}
        self._project.clusters = [c for c in self._project.clusters if c.uid not in removed_uids]
        for server in self._project.servers:
            if server.cluster_uid in removed_uids:
                server.cluster_uid = ""
        for vm in self._project.vms:
            if vm.cluster_uid in removed_uids:
                vm.cluster_uid = ""
        self.clusters_changed.emit()
        self.servers_changed.emit()
        self.vms_changed.emit()
        self._notify()

    def clear_clusters(self) -> None:
        self._push_undo_snapshot()
        self._project.clusters = []
        for server in self._project.servers:
            server.cluster_uid = ""
        for vm in self._project.vms:
            vm.cluster_uid = ""
        self.clusters_changed.emit()
        self.servers_changed.emit()
        self.vms_changed.emit()
        self._notify()

    def import_vlans_csv(self, path: str | Path, replace: bool = False) -> int:
        new_vlans = csv_io.import_vlans(path)
        self._push_undo_snapshot()
        self._project.vlans = new_vlans if replace else self._project.vlans + new_vlans
        self._notify(self.network_changed)
        return len(new_vlans)

    def export_vlans_csv(self, path: str | Path) -> None:
        csv_io.export_vlans(path, self._project.vlans)

    def import_storages_csv(self, path: str | Path, replace: bool = False) -> int:
        new_storages = csv_io.import_storages(path)
        self._push_undo_snapshot()
        self._project.storages = new_storages if replace else self._project.storages + new_storages
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

    def add_vms(self, vms: list[VirtualMachine], replace: bool = False) -> None:
        """Batch add - a single changed signal for the whole group (used by
        the Smart Import wizard and CSV import). replace=True clears every
        existing VM first - cascades to FailoverAssignment records the
        same way clear_vms() does, since an assignment pointing at a VM
        that no longer exists would be orphaned."""
        self._push_undo_snapshot()
        if replace:
            self._project.vms = list(vms)
            self._project.failover_assignments = []
        else:
            self._project.vms.extend(vms)
        self._notify(self.vms_changed)

    def update_vm(self, index: int, vm: VirtualMachine) -> None:
        self._push_undo_snapshot()
        self._project.vms[index] = vm
        self._notify(self.vms_changed)

    def remove_vms(self, vms: list[VirtualMachine]) -> None:
        self._push_undo_snapshot()
        removed_uids = {v.uid for v in vms}
        self._project.vms = [v for v in self._project.vms if v.uid not in removed_uids]
        self._project.failover_assignments = [
            a for a in self._project.failover_assignments if a.vm_uid not in removed_uids
        ]
        self._notify(self.vms_changed)

    def clear_vms(self) -> None:
        self._push_undo_snapshot()
        self._project.vms = []
        self._project.failover_assignments = []
        self._notify(self.vms_changed)

    def set_all_vms_workload_tier(self, tier: str) -> None:
        """Bulk-sets workload_tier on every VM at once - one undo snapshot
        for the whole action, not one per VM, so a single Ctrl+Z reverts
        it all. A quick way to size a whole cluster without editing VMs
        one by one first.

        See bulk_set_vm_fields below for the general-purpose version."""
        self._push_undo_snapshot()
        for vm in self._project.vms:
            vm.workload_tier = tier
        self._notify(self.vms_changed)

    def bulk_set_server_fields(self, servers: list[Server], updates: dict) -> None:
        """Sets one or more fields to given values on every given
        server - one undo snapshot for the whole selection, however
        many servers and fields are involved. Lets a mis-entered value
        (e.g. disk count/size typed wrong on several identical servers)
        be fixed in one action instead of editing each server's dialog
        separately."""
        if not servers or not updates:
            return
        self._push_undo_snapshot()
        for server in servers:
            for field, value in updates.items():
                setattr(server, field, value)
        self._notify(self.servers_changed)

    def bulk_set_storage_fields(self, storages: list[Storage], updates: dict) -> None:
        if not storages or not updates:
            return
        self._push_undo_snapshot()
        for storage in storages:
            for field, value in updates.items():
                setattr(storage, field, value)
        self._notify(self.storages_changed)

    def bulk_set_vm_fields(self, vms: list[VirtualMachine], updates: dict) -> None:
        if not vms or not updates:
            return
        self._push_undo_snapshot()
        for vm in vms:
            for field, value in updates.items():
                setattr(vm, field, value)
        self._notify(self.vms_changed)

    def set_failover_assignment_for_vms(
        self, vms: list[VirtualMachine], target_site: str, assigned: bool,
    ) -> None:
        """Bulk create/remove a FailoverAssignment targeting target_site
        for each given VM - one undo snapshot for the whole selection.
        Turning it ON creates an assignment (defaulting footprint to
        match the VM's own vcpu/ram/disk) unless one already exists for
        that VM+site; turning it OFF only removes the assignment for
        target_site - any assignments to OTHER sites are untouched, so
        toggling DR off doesn't accidentally drop a VM's DR2 assignment."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            existing = next(
                (a for a in self._project.failover_assignments
                 if a.vm_uid == vm.uid and a.target_site == target_site),
                None,
            )
            if assigned:
                if existing is None:
                    new_assignment = FailoverAssignment.create_default()
                    new_assignment.vm_uid = vm.uid
                    new_assignment.target_site = target_site
                    new_assignment.vcpu = vm.vcpu
                    new_assignment.ram_gb = vm.ram_gb
                    new_assignment.disk_gb = vm.disk_gb
                    self._project.failover_assignments.append(new_assignment)
            elif existing is not None:
                self._project.failover_assignments.remove(existing)
        self._notify(self.vms_changed)

    def set_failover_assignment_for_all_vms(self, target_site: str, assigned: bool) -> None:
        """Same as set_failover_assignment_for_vms, but applied to every
        VM in the project at once."""
        self.set_failover_assignment_for_vms(self._project.vms, target_site, assigned)

    # ------------------------------------------------------------------
    # Failover Assignments (standalone list - see FailoverAssignment's
    # docstring for why this isn't nested on VirtualMachine)
    # ------------------------------------------------------------------

    def add_failover_assignment(self, assignment: FailoverAssignment) -> None:
        self._push_undo_snapshot()
        self._project.failover_assignments.append(assignment)
        self._notify(self.vms_changed)

    def add_failover_assignments(self, assignments: list[FailoverAssignment]) -> None:
        """Batch add - one undo step for the whole group, used by the
        VMs table's right-click 'Assign to Failover' action so
        assigning several VMs at once to the same target site reverts
        as a single Ctrl+Z."""
        if not assignments:
            return
        self._push_undo_snapshot()
        self._project.failover_assignments.extend(assignments)
        self._notify(self.vms_changed)

    def update_failover_assignment(self, index: int, assignment: FailoverAssignment) -> None:
        self._push_undo_snapshot()
        self._project.failover_assignments[index] = assignment
        self._notify(self.vms_changed)

    def remove_failover_assignments(self, assignments: list[FailoverAssignment]) -> None:
        self._push_undo_snapshot()
        removed_uids = {a.uid for a in assignments}
        self._project.failover_assignments = [
            a for a in self._project.failover_assignments if a.uid not in removed_uids
        ]
        self._notify(self.vms_changed)

    def clear_failover_assignments(self) -> None:
        self._push_undo_snapshot()
        self._project.failover_assignments = []
        self._notify(self.vms_changed)

    def set_failover_assignment_confirmed(
        self, assignments: list[FailoverAssignment], confirmed: bool,
    ) -> None:
        """Marks a footprint that exceeds the VM's current size as
        intentional (e.g. a deliberately over-provisioned warm standby)
        rather than stale - silences the Attention Needed warning and
        the table's orange marker for exactly these assignments, one
        undo step for the whole selection."""
        if not assignments:
            return
        self._push_undo_snapshot()
        target_uids = {a.uid for a in assignments}
        for a in self._project.failover_assignments:
            if a.uid in target_uids:
                a.footprint_confirmed = confirmed
        self._notify(self.vms_changed)

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
        """Moves the given VMs to a different site (Primary/DR/etc.) - a
        DIFFERENT concept from a FailoverAssignment (which targets a VM
        to fail over to a site while it keeps living on its CURRENT
        site). This actually relocates where the VM "lives". One undo
        snapshot for the whole selection."""
        if not vms:
            return
        self._push_undo_snapshot()
        for vm in vms:
            vm.site = site
        self._notify(self.vms_changed)

    def import_vms_csv(self, path: str | Path, replace: bool = False) -> int:
        new_vms = csv_io.import_vms(path)
        self._push_undo_snapshot()
        self._project.vms = new_vms if replace else self._project.vms + new_vms
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

    def import_switches_csv(self, path: str | Path, replace: bool = False) -> int:
        new_switches = csv_io.import_switches(path)
        self._push_undo_snapshot()
        self._project.switches = new_switches if replace else self._project.switches + new_switches
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
        removed_uids = {c.uid for c in connections}
        self._project.connections = [
            c for c in self._project.connections if c.uid not in removed_uids
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
