"""Turns (header, rows) + an ImportProfile into ClusterSizer VirtualMachine
objects. Pure logic, no Qt - the wizard dialog is just a UI shell around
this."""

import uuid

from src.models.import_profile import ImportProfile
from src.models.virtual_machine import VirtualMachine
from src.persistence.units import parse_size_to_gb, parse_int, parse_bool


def best_matching_profile(header: list[str], profiles: list[ImportProfile]) -> ImportProfile | None:
    """Picks the profile whose expected source columns overlap the most
    with this file's actual header - so re-importing a known tool's export
    needs zero manual re-mapping. Returns None if nothing overlaps at all."""
    header_set = set(header)
    best = None
    best_overlap = 0
    for profile in profiles:
        overlap = len(profile.header_signature() & header_set)
        if overlap > best_overlap:
            best_overlap = overlap
            best = profile
    return best if best_overlap > 0 else None


def convert_rows(
    rows: list[dict], profile: ImportProfile, site: str
) -> tuple[list[VirtualMachine], int]:
    """Returns (converted VMs, number of rows skipped due to a name prefix
    match in profile.skip_name_prefixes, e.g. vCLS-* system VMs)."""

    name_col = profile.mapping_for("name")
    vcpu_col = profile.mapping_for("vcpu")
    ram_col = profile.mapping_for("ram_gb")
    disk_col = profile.mapping_for("disk_gb")
    power_col = profile.mapping_for("powered_on")
    site_col = profile.mapping_for("site")
    notes_col = profile.mapping_for("notes")

    vms = []
    skipped = 0

    for row in rows:
        name = str(row.get(name_col.source_column, "")).strip() if name_col else ""
        if not name:
            continue
        if any(name.startswith(prefix) for prefix in profile.skip_name_prefixes):
            skipped += 1
            continue

        vcpu = parse_int(row.get(vcpu_col.source_column), default=1) if vcpu_col else 1
        ram_gb = parse_size_to_gb(row.get(ram_col.source_column), ram_col.unit) if ram_col else 0.0
        disk_gb = parse_size_to_gb(row.get(disk_col.source_column), disk_col.unit) if disk_col else 0.0
        powered_on = (
            parse_bool(row.get(power_col.source_column), profile.powered_on_value)
            if power_col else True
        )
        row_site = str(row.get(site_col.source_column, site)).strip() if site_col else site
        if row_site not in ("Primary", "DR"):
            row_site = site
        notes = str(row.get(notes_col.source_column, "")).strip() if notes_col else ""

        vms.append(VirtualMachine(
            uid=str(uuid.uuid4()),
            name=name,
            site=row_site,
            vcpu=vcpu,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            powered_on=powered_on,
            dr_protected=False,
            dr_vcpu=vcpu,
            dr_ram_gb=ram_gb,
            dr_disk_gb=disk_gb,
            notes=notes,
        ))

    return vms, skipped
