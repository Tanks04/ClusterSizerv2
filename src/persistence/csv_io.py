"""CSV import/export for servers, storage, VMs, switches, and network
connections.

The format is deliberately simple (one row = one object, header = field
names) so a sysadmin can create/edit it in Excel without extra tools.

Every import_* function checks that the CSV header contains ALL expected
columns for that type before it starts parsing - this prevents e.g.
importing a VM CSV on the Servers tab (and vice versa), instead of
silently creating rows with default values.
"""

import csv
from pathlib import Path

from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.workload_tier import WORKLOAD_TIER_NAMES, DEFAULT_WORKLOAD_TIER
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.vlan import Vlan


class CsvSchemaError(ValueError):
    """CSV header does not match the expected data type (e.g. trying to
    import a VM CSV on the Servers tab)."""


SERVER_FIELDS = [
    "name", "site", "vendor", "model", "cpu_vendor", "cpu_model",
    "sockets", "cores_per_socket", "threads_per_core", "hyperthreading_enabled",
    "ram_gb", "cpu_frequency", "warranty_expiry", "ip_address", "cluster_name",
    "serial_number", "bmc_ip", "hypervisor_vendor", "hypervisor_version",
    "nic_1g", "nic_10g", "nic_25g", "nic_40g", "nic_100g", "nic_fc", "nic_sas",
    "rack_units", "power_watts", "price", "local_disk_raw_tb",
    "enabled", "notes",
]
SERVER_CORE_FIELDS = ["name", "site", "sockets", "cores_per_socket"]

STORAGE_FIELDS = [
    "name", "site", "vendor", "model", "raw_capacity_tb",
    "usable_capacity_tb", "raid_overhead_percent", "is_hci",
    "ports_1g", "ports_10g", "ports_25g", "ports_40g", "ports_100g", "ports_fc", "ports_sas",
    "rack_units", "power_watts", "price",
    "notes",
]
STORAGE_CORE_FIELDS = ["name", "site", "raw_capacity_tb", "usable_capacity_tb"]

BACKUP_DESTINATION_FIELDS = [
    "name", "site", "destination_type", "backup_software",
    "raw_capacity_tb", "dedup_ratio", "is_offsite", "is_immutable",
    "price", "location", "notes",
]
BACKUP_DESTINATION_CORE_FIELDS = ["name", "site", "destination_type", "backup_software"]

VM_FIELDS = [
    "name", "site", "vcpu", "ram_gb", "disk_gb", "powered_on",
    "workload_tier", "dr_category", "ip_address", "os", "notes",
]
VM_CORE_FIELDS = ["name", "site", "vcpu", "ram_gb", "disk_gb"]

SWITCH_FIELDS = [
    "name", "site", "vendor", "model", "switch_type",
    "ports_1g", "ports_10g", "ports_25g", "ports_40g", "ports_100g", "ports_fc", "ports_sas",
    "rack_units", "power_watts", "price",
    "notes",
]
SWITCH_CORE_FIELDS = ["name", "site", "switch_type"]

MAINTENANCE_ITEM_FIELDS = [
    "name", "category", "cost", "duration_months",
    "start_date", "expiry_date", "applies_to", "notes",
]
MAINTENANCE_ITEM_CORE_FIELDS = ["name", "category", "cost", "duration_months"]

VLAN_FIELDS = [
    "name", "site", "network", "gateway", "notes",
]
VLAN_CORE_FIELDS = ["name", "site", "network"]

# server_name / switch_name / storage_name: exactly two of the three
# should be filled per row - which two determines the connection kind
# (Server<->Switch, Storage<->Switch, or Server<->Storage direct-attach).
CONNECTION_FIELDS = [
    "server_name", "switch_name", "storage_name", "speed", "media",
    "switch_port_label", "purpose", "notes",
]
CONNECTION_CORE_FIELDS = ["server_name", "switch_name", "storage_name", "speed"]


def _read_rows(path: str | Path, expected_fields: list[str], kind: str, core_fields: list[str] | None = None) -> list[dict]:
    """Only validates against core_fields (a small, foundational subset
    genuinely unlikely to ever change) rather than the full expected_fields
    list - a CSV exported by an older app version simply won't have a
    newer optional column (e.g. dr_category, hypervisor_vendor, location)
    yet, and rejecting the whole file over that would be wrong: every
    import_*() function already tolerates a missing optional column via
    row.get(field, default), so the validation gate was stricter than the
    parsing it's guarding. Falls back to the full list if core_fields
    isn't given (kept for any future caller that doesn't specify one)."""
    required = core_fields if core_fields is not None else expected_fields
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = set(reader.fieldnames or [])
        missing = [field for field in required if field not in header]
        if missing:
            raise CsvSchemaError(
                f"This doesn't look like a {kind} CSV - missing columns: {', '.join(missing)}. "
                f"Check that you didn't import the wrong file (e.g. a VMs CSV on the Servers tab)."
            )
        return list(reader)


def _write_rows(path: str | Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text == "":
        return default
    return text not in ("false", "0", "no")


# ----------------------------------------------------------------------
# Servers
# ----------------------------------------------------------------------

def import_servers(path: str | Path) -> list[Server]:
    servers = []
    for row in _read_rows(path, SERVER_FIELDS, "Servers", SERVER_CORE_FIELDS):
        default = Server.create_default()
        servers.append(
            Server(
                uid=default.uid,
                name=row.get("name", ""),
                site=row.get("site") or "Primary",
                vendor=row.get("vendor", ""),
                model=row.get("model", ""),
                cpu_vendor=row.get("cpu_vendor", "Intel"),
                cpu_model=row.get("cpu_model", ""),
                sockets=int(float(row.get("sockets") or 2)),
                cores_per_socket=int(float(row.get("cores_per_socket") or 16)),
                threads_per_core=int(float(row.get("threads_per_core") or 2)),
                hyperthreading_enabled=_bool(row.get("hyperthreading_enabled"), default=True),
                ram_gb=int(float(row.get("ram_gb") or 256)),
                cpu_frequency=float(row.get("cpu_frequency") or 2.5),
                warranty_expiry=row.get("warranty_expiry", "") or "",
                ip_address=row.get("ip_address", "") or "",
                cluster_name=row.get("cluster_name", "") or "",
                serial_number=row.get("serial_number", "") or "",
                bmc_ip=row.get("bmc_ip", "") or "",
                hypervisor_vendor=row.get("hypervisor_vendor", "") or "",
                hypervisor_version=row.get("hypervisor_version", "") or "",
                rack_units=int(float(row.get("rack_units") or 0)),
                price=float(row.get("price") or 0),
                local_disk_raw_tb=float(row.get("local_disk_raw_tb") or 0),
                power_watts=float(row.get("power_watts") or 0),
                nic_1g=int(float(row.get("nic_1g") or 0)),
                nic_10g=int(float(row.get("nic_10g") or 0)),
                nic_25g=int(float(row.get("nic_25g") or 0)),
                nic_40g=int(float(row.get("nic_40g") or 0)),
                nic_100g=int(float(row.get("nic_100g") or 0)),
                nic_fc=int(float(row.get("nic_fc") or 0)),
                nic_sas=int(float(row.get("nic_sas") or 0)),
                enabled=_bool(row.get("enabled"), default=True),
                notes=row.get("notes", "") or "",
            )
        )
    return servers


def export_servers(path: str | Path, servers: list[Server]) -> None:
    rows = [{field: getattr(s, field) for field in SERVER_FIELDS} for s in servers]
    _write_rows(path, SERVER_FIELDS, rows)


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------

def import_storages(path: str | Path) -> list[Storage]:
    storages = []
    for row in _read_rows(path, STORAGE_FIELDS, "Storage", STORAGE_CORE_FIELDS):
        default = Storage.create_default()
        storages.append(
            Storage(
                uid=default.uid,
                name=row.get("name", ""),
                site=row.get("site") or "Primary",
                vendor=row.get("vendor", ""),
                model=row.get("model", ""),
                raw_capacity_tb=float(row.get("raw_capacity_tb") or 0),
                usable_capacity_tb=float(row.get("usable_capacity_tb") or 0),
                raid_overhead_percent=float(row.get("raid_overhead_percent") or 0),
                ports_1g=int(float(row.get("ports_1g") or 0)),
                ports_10g=int(float(row.get("ports_10g") or 0)),
                ports_25g=int(float(row.get("ports_25g") or 0)),
                ports_40g=int(float(row.get("ports_40g") or 0)),
                ports_100g=int(float(row.get("ports_100g") or 0)),
                ports_fc=int(float(row.get("ports_fc") or 0)),
                ports_sas=int(float(row.get("ports_sas") or 0)),
                rack_units=int(float(row.get("rack_units") or 0)),
                power_watts=float(row.get("power_watts") or 0),
                price=float(row.get("price") or 0),
                is_hci=_bool(row.get("is_hci"), default=False),
                notes=row.get("notes", "") or "",
            )
        )
    return storages


def export_storages(path: str | Path, storages: list[Storage]) -> None:
    rows = [{field: getattr(s, field) for field in STORAGE_FIELDS} for s in storages]
    _write_rows(path, STORAGE_FIELDS, rows)


def import_backup_destinations(path: str | Path) -> list[BackupDestination]:
    destinations = []
    for row in _read_rows(path, BACKUP_DESTINATION_FIELDS, "Backup Destination", BACKUP_DESTINATION_CORE_FIELDS):
        default = BackupDestination.create_default()
        destinations.append(
            BackupDestination(
                uid=default.uid,
                name=row.get("name", ""),
                site=row.get("site") or "Primary",
                destination_type=row.get("destination_type") or "Disk Appliance",
                backup_software=row.get("backup_software", "") or "",
                raw_capacity_tb=float(row.get("raw_capacity_tb") or 0),
                dedup_ratio=float(row.get("dedup_ratio") or 1.0),
                is_offsite=_bool(row.get("is_offsite"), default=False),
                is_immutable=_bool(row.get("is_immutable"), default=False),
                price=float(row.get("price") or 0),
                location=row.get("location", "") or "",
                notes=row.get("notes", "") or "",
            )
        )
    return destinations


def export_backup_destinations(path: str | Path, destinations: list[BackupDestination]) -> None:
    rows = [{field: getattr(d, field) for field in BACKUP_DESTINATION_FIELDS} for d in destinations]
    _write_rows(path, BACKUP_DESTINATION_FIELDS, rows)


def import_maintenance_items(path: str | Path) -> list[MaintenanceItem]:
    items = []
    for row in _read_rows(path, MAINTENANCE_ITEM_FIELDS, "Maintenance Item", MAINTENANCE_ITEM_CORE_FIELDS):
        default = MaintenanceItem.create_default()
        items.append(
            MaintenanceItem(
                uid=default.uid,
                name=row.get("name", "") or "",
                category=row.get("category") or "License",
                cost=float(row.get("cost") or 0),
                duration_months=int(float(row.get("duration_months") or 12)),
                start_date=row.get("start_date", "") or "",
                expiry_date=row.get("expiry_date", "") or "",
                applies_to=row.get("applies_to", "") or "",
                notes=row.get("notes", "") or "",
            )
        )
    return items


def export_maintenance_items(path: str | Path, items: list[MaintenanceItem]) -> None:
    rows = [{field: getattr(i, field) for field in MAINTENANCE_ITEM_FIELDS} for i in items]
    _write_rows(path, MAINTENANCE_ITEM_FIELDS, rows)


# ----------------------------------------------------------------------
# VLANs
# ----------------------------------------------------------------------

def import_vlans(path: str | Path) -> list[Vlan]:
    vlans = []
    for row in _read_rows(path, VLAN_FIELDS, "VLAN", VLAN_CORE_FIELDS):
        default = Vlan.create_default()
        vlans.append(
            Vlan(
                uid=default.uid,
                name=row.get("name", "") or "",
                site=row.get("site") or "Primary",
                network=row.get("network", "") or "",
                gateway=row.get("gateway", "") or "",
                notes=row.get("notes", "") or "",
            )
        )
    return vlans


def export_vlans(path: str | Path, vlans: list[Vlan]) -> None:
    rows = [{field: getattr(v, field) for field in VLAN_FIELDS} for v in vlans]
    _write_rows(path, VLAN_FIELDS, rows)


# ----------------------------------------------------------------------
# Virtual machines
# ----------------------------------------------------------------------

def import_vms(path: str | Path) -> list[VirtualMachine]:
    vms = []
    for row in _read_rows(path, VM_FIELDS, "VMs", VM_CORE_FIELDS):
        default = VirtualMachine.create_default()
        vcpu = int(float(row.get("vcpu") or 2))
        ram_gb = float(row.get("ram_gb") or 8)
        disk_gb = float(row.get("disk_gb") or 100)
        workload_tier = row.get("workload_tier") or DEFAULT_WORKLOAD_TIER
        if workload_tier not in WORKLOAD_TIER_NAMES:
            workload_tier = DEFAULT_WORKLOAD_TIER
        vms.append(
            VirtualMachine(
                uid=default.uid,
                name=row.get("name", ""),
                site=row.get("site") or "Primary",
                vcpu=vcpu,
                ram_gb=ram_gb,
                disk_gb=disk_gb,
                powered_on=_bool(row.get("powered_on"), default=True),
                workload_tier=workload_tier,
                dr_category=row.get("dr_category", "") or "",
                ip_address=row.get("ip_address", "") or "",
                os=row.get("os", "") or "",
                notes=row.get("notes", "") or "",
            )
        )
    return vms


def export_vms(path: str | Path, vms: list[VirtualMachine]) -> None:
    rows = [{field: getattr(v, field) for field in VM_FIELDS} for v in vms]
    _write_rows(path, VM_FIELDS, rows)


# ----------------------------------------------------------------------
# Network switches
# ----------------------------------------------------------------------

def import_switches(path: str | Path) -> list[NetworkSwitch]:
    switches = []
    for row in _read_rows(path, SWITCH_FIELDS, "Network Switches", SWITCH_CORE_FIELDS):
        default = NetworkSwitch.create_default()
        switches.append(
            NetworkSwitch(
                uid=default.uid,
                name=row.get("name", ""),
                site=row.get("site") or "Primary",
                vendor=row.get("vendor", ""),
                model=row.get("model", ""),
                switch_type=row.get("switch_type") or "LAN",
                ports_1g=int(float(row.get("ports_1g") or 0)),
                ports_10g=int(float(row.get("ports_10g") or 0)),
                ports_25g=int(float(row.get("ports_25g") or 0)),
                ports_40g=int(float(row.get("ports_40g") or 0)),
                ports_100g=int(float(row.get("ports_100g") or 0)),
                ports_fc=int(float(row.get("ports_fc") or 0)),
                ports_sas=int(float(row.get("ports_sas") or 0)),
                rack_units=int(float(row.get("rack_units") or 0)),
                power_watts=float(row.get("power_watts") or 0),
                price=float(row.get("price") or 0),
                notes=row.get("notes", "") or "",
            )
        )
    return switches


def export_switches(path: str | Path, switches: list[NetworkSwitch]) -> None:
    rows = [{field: getattr(s, field) for field in SWITCH_FIELDS} for s in switches]
    _write_rows(path, SWITCH_FIELDS, rows)


# ----------------------------------------------------------------------
# Network connections
# ----------------------------------------------------------------------
# The CSV format references server/switch/storage by NAME (not uid) since
# that's easier to hand-edit - import resolves them to current uids by
# name. Exactly two of the three name columns should be filled per row;
# whichever two determines the connection kind. If a referenced name
# doesn't exist in the project, or fewer/more than two names are given,
# the row is skipped (counted in "skipped").

def import_connections(
    path: str | Path,
    servers: list[Server],
    switches: list[NetworkSwitch],
    storages: list[Storage],
) -> tuple[list[NetworkConnection], int]:
    server_by_name = {s.name: s.uid for s in servers if s.name}
    switch_by_name = {s.name: s.uid for s in switches if s.name}
    storage_by_name = {s.name: s.uid for s in storages if s.name}

    connections = []
    skipped = 0

    for row in _read_rows(path, CONNECTION_FIELDS, "Network Connections", CONNECTION_CORE_FIELDS):
        server_uid = server_by_name.get(row.get("server_name", "") or "")
        switch_uid = switch_by_name.get(row.get("switch_name", "") or "")
        storage_uid = storage_by_name.get(row.get("storage_name", "") or "")

        endpoints_filled = sum(1 for u in (server_uid, switch_uid, storage_uid) if u)
        if endpoints_filled != 2:
            skipped += 1
            continue

        default = NetworkConnection.create_default()
        connections.append(
            NetworkConnection(
                uid=default.uid,
                server_uid=server_uid or "",
                switch_uid=switch_uid or "",
                storage_uid=storage_uid or "",
                speed=row.get("speed") or "25G",
                media=row.get("media") or "SFP28",
                switch_port_label=row.get("switch_port_label", "") or "",
                purpose=row.get("purpose") or "Data",
                notes=row.get("notes", "") or "",
            )
        )

    return connections, skipped


def export_connections(
    path: str | Path,
    connections: list[NetworkConnection],
    servers: list[Server],
    switches: list[NetworkSwitch],
    storages: list[Storage],
) -> None:
    server_name_by_uid = {s.uid: s.name for s in servers}
    switch_name_by_uid = {s.uid: s.name for s in switches}
    storage_name_by_uid = {s.uid: s.name for s in storages}

    rows = []
    for c in connections:
        rows.append({
            "server_name": server_name_by_uid.get(c.server_uid, "(unknown)") if c.server_uid else "",
            "switch_name": switch_name_by_uid.get(c.switch_uid, "(unknown)") if c.switch_uid else "",
            "storage_name": storage_name_by_uid.get(c.storage_uid, "(unknown)") if c.storage_uid else "",
            "speed": c.speed,
            "media": c.media,
            "switch_port_label": c.switch_port_label,
            "purpose": c.purpose,
            "notes": c.notes,
        })

    _write_rows(path, CONNECTION_FIELDS, rows)
