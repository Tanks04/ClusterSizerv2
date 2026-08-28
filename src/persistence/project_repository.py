"""Saving/loading a ClusterProject as a JSON (.clsz) file."""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject, ON_PREMISE
from src.models.server import Server
from src.models.storage import Storage, StorageShelf
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.vlan import Vlan

FILE_EXTENSION = ".clsz"
SCHEMA_VERSION = 7


@dataclass
class LoadedProject:
    """load_project()'s return value. Thresholds live on ProjectService, not
    on ClusterProject (see the model/service layer boundary) - this widens
    the return just enough to carry both back out of persistence
    explicitly, without a global/singleton to smuggle thresholds across
    the boundary. Callers that don't care about thresholds (ComparePage
    loading a read-only scenario snapshot - Compare always evaluates both
    scenarios under the service's live thresholds) simply ignore
    `.thresholds` and use `.project`."""
    project: ClusterProject
    thresholds: Thresholds


def save_project(
    project: ClusterProject, path: str | Path, thresholds: Thresholds | None = None
) -> None:
    data = {
        "schema_version": SCHEMA_VERSION,
        "name": project.name,
        "primary_deployment_model": project.primary_deployment_model,
        "dr_deployment_model": project.dr_deployment_model,
        "primary_rack_capacity_u": project.primary_rack_capacity_u,
        "dr_rack_capacity_u": project.dr_rack_capacity_u,
        "servers": [asdict(s) for s in project.servers],
        "storages": [asdict(s) for s in project.storages],
        "vms": [asdict(v) for v in project.vms],
        "switches": [asdict(s) for s in project.switches],
        "connections": [asdict(c) for c in project.connections],
        "backup_destinations": [asdict(d) for d in project.backup_destinations],
        "maintenance_items": [asdict(i) for i in project.maintenance_items],
        "vlans": [asdict(v) for v in project.vlans],
        "thresholds": asdict(thresholds if thresholds is not None else Thresholds()),
    }

    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> LoadedProject:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    project = ClusterProject(name=raw.get("name", "New Project"))
    project.primary_deployment_model = raw.get("primary_deployment_model", ON_PREMISE)
    project.dr_deployment_model = raw.get("dr_deployment_model", ON_PREMISE)
    project.primary_rack_capacity_u = raw.get("primary_rack_capacity_u", 0)
    project.dr_rack_capacity_u = raw.get("dr_rack_capacity_u", 0)

    project.servers = [_build(Server, _migrate_price(row)) for row in raw.get("servers", [])]
    project.storages = [_build_storage(row) for row in raw.get("storages", [])]
    project.vms = [_build(VirtualMachine, row) for row in raw.get("vms", [])]
    project.switches = [_build(NetworkSwitch, _migrate_price(row)) for row in raw.get("switches", [])]
    project.connections = [_build(NetworkConnection, row) for row in raw.get("connections", [])]
    project.backup_destinations = [
        _build(BackupDestination, _migrate_price(row)) for row in raw.get("backup_destinations", [])
    ]
    project.maintenance_items = [
        _build(MaintenanceItem, row) for row in raw.get("maintenance_items", [])
    ]
    project.vlans = [_build(Vlan, row) for row in raw.get("vlans", [])]

    # Absent for files saved before schema v3 - fall back to defaults
    # rather than failing, same tolerance _build() already gives every
    # entity field.
    thresholds_data = raw.get("thresholds")
    thresholds = _build(Thresholds, thresholds_data) if thresholds_data else Thresholds()

    return LoadedProject(project=project, thresholds=thresholds)


def _build(cls, row: dict):
    """Builds a dataclass instance while ignoring unknown fields (e.g. a file
    saved by an older/newer app version) - prevents opening a project from
    breaking over minor schema drift. Missing fields (e.g. a .clsz saved
    before the nic_* fields were added to Server) fall back to the
    dataclass default."""
    known = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in row.items() if k in known}
    return cls(**filtered)


def _migrate_price(row: dict) -> dict:
    """v6 files had separate unit_cost/unit_price (a sales-quote-style
    cost/price/margin split); v7 simplified pricing down to one plain
    `price` field (this app just totals up what equipment costs, not a
    quoting tool). Best-effort migration for old files: prefer the old
    unit_price (closer in spirit to the new single price - it's what
    would actually be paid), falling back to unit_cost if unit_price
    was never set, so upgrading doesn't silently zero out pricing data
    someone already entered. A no-op for rows that already have `price`
    or never had either old field."""
    if "price" in row:
        return row
    if "unit_price" in row or "unit_cost" in row:
        row = dict(row)
        row["price"] = row.get("unit_price") or row.get("unit_cost") or 0.0
    return row


def _build_storage(row: dict) -> Storage:
    """_build() only does a SHALLOW field filter - Storage.expansion_shelves
    is a list of nested StorageShelf objects, which would otherwise come
    back as plain dicts (breaking .rack_units/.power_watts attribute
    access) since JSON has no concept of a nested dataclass. Reconstruct
    those explicitly; everything else goes through the normal helper."""
    storage = _build(Storage, _migrate_price(row))
    known_shelf_fields = {f.name for f in fields(StorageShelf)}
    storage.expansion_shelves = [
        StorageShelf(**{k: v for k, v in _migrate_price(shelf).items() if k in known_shelf_fields})
        for shelf in row.get("expansion_shelves", [])
    ]
    return storage
