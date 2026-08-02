"""Spremanje/učitavanje ClusterProject-a kao JSON (.clsz) datoteke."""

import json
from dataclasses import asdict, fields
from pathlib import Path

from src.models.cluster_project import ClusterProject
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection

FILE_EXTENSION = ".clsz"
SCHEMA_VERSION = 2


def save_project(project: ClusterProject, path: str | Path) -> None:
    data = {
        "schema_version": SCHEMA_VERSION,
        "name": project.name,
        "servers": [asdict(s) for s in project.servers],
        "storages": [asdict(s) for s in project.storages],
        "vms": [asdict(v) for v in project.vms],
        "switches": [asdict(s) for s in project.switches],
        "connections": [asdict(c) for c in project.connections],
    }

    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> ClusterProject:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    project = ClusterProject(name=raw.get("name", "New Project"))

    project.servers = [_build(Server, row) for row in raw.get("servers", [])]
    project.storages = [_build(Storage, row) for row in raw.get("storages", [])]
    project.vms = [_build(VirtualMachine, row) for row in raw.get("vms", [])]
    project.switches = [_build(NetworkSwitch, row) for row in raw.get("switches", [])]
    project.connections = [_build(NetworkConnection, row) for row in raw.get("connections", [])]

    return project


def _build(cls, row: dict):
    """Gradi dataclass instancu ignorirajući nepoznata polja (npr. datoteka
    spremljena starijom/novijom verzijom aplikacije) - sprječava da otvaranje
    projekta pukne zbog manjeg schema drifta. Nedostajuća polja (npr. .clsz
    spremljen prije nego su nic_* polja dodana na Server) padaju na default
    vrijednost dataclass-a."""
    known = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in row.items() if k in known}
    return cls(**filtered)
