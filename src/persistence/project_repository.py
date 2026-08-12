"""Saving/loading a ClusterProject as a JSON (.clsz) file."""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection

FILE_EXTENSION = ".clsz"
SCHEMA_VERSION = 3


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
        "servers": [asdict(s) for s in project.servers],
        "storages": [asdict(s) for s in project.storages],
        "vms": [asdict(v) for v in project.vms],
        "switches": [asdict(s) for s in project.switches],
        "connections": [asdict(c) for c in project.connections],
        "thresholds": asdict(thresholds if thresholds is not None else Thresholds()),
    }

    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> LoadedProject:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    project = ClusterProject(name=raw.get("name", "New Project"))

    project.servers = [_build(Server, row) for row in raw.get("servers", [])]
    project.storages = [_build(Storage, row) for row in raw.get("storages", [])]
    project.vms = [_build(VirtualMachine, row) for row in raw.get("vms", [])]
    project.switches = [_build(NetworkSwitch, row) for row in raw.get("switches", [])]
    project.connections = [_build(NetworkConnection, row) for row in raw.get("connections", [])]

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
