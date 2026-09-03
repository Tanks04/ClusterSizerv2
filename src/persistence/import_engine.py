"""Turns (header, rows) + an ImportProfile into ClusterSizer VirtualMachine
objects. Pure logic, no Qt - the wizard dialog is just a UI shell around
this."""

import uuid

from src.models.import_profile import ImportProfile
from src.models.virtual_machine import VirtualMachine
from src.persistence.units import parse_bool, parse_int, parse_size_to_gb


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


def _build_sheet_index(sheet_rows: list[dict], join_key_column: str) -> dict[str, dict]:
    """Maps join-key value -> row, for fast lookup when pulling a field
    from a non-primary sheet. Last row wins on a duplicate key (matches
    how a real export would rarely have true duplicates on its identity
    column - if it does, this is a reasonable, simple tie-break rather
    than silently picking an arbitrary one via first-match)."""
    index = {}
    for row in sheet_rows:
        key = row.get(join_key_column)
        if key not in (None, ""):
            index[str(key).strip()] = row
    return index


def convert_rows(
    rows: list[dict],
    profile: ImportProfile,
    site: str,
    sheets_data: dict[str, list[dict]] | None = None,
    join_key_column: str | None = None,
    valid_sites: list[str] | None = None,
) -> tuple[list[VirtualMachine], int]:
    """Returns (converted VMs, number of rows skipped due to a name prefix
    match in profile.skip_name_prefixes, e.g. vCLS-* system VMs).

    sheets_data: other sheets in the same workbook, keyed by sheet name -
    only needed if any ColumnMapping.source_sheet points away from the
    primary sheet (`rows`). join_key_column defaults to the name field's
    own source_column, on the assumption that the SAME literal column
    name identifies the same entity across sheets (true for RVTools -
    "VM" is consistent across vInfo/vCPU/vMemory/vPartition/etc; may not
    hold for other tools' multi-sheet exports, in which case cross-sheet
    fields simply won't find a match and fall back to blank/default,
    never crash).
    """
    name_col = profile.mapping_for("name")
    vcpu_col = profile.mapping_for("vcpu")
    ram_col = profile.mapping_for("ram_gb")
    disk_col = profile.mapping_for("disk_gb")
    power_col = profile.mapping_for("powered_on")
    site_col = profile.mapping_for("site")
    notes_col = profile.mapping_for("notes")
    ip_col = profile.mapping_for("ip_address")
    os_col = profile.mapping_for("os")

    if join_key_column is None:
        join_key_column = name_col.source_column if name_col else ""

    sheets_data = sheets_data or {}
    sheet_indexes: dict[str, dict[str, dict]] = {}

    def _resolve(row: dict, mapping) -> object:
        """Reads mapping.source_column from the right row - the primary
        row itself, or the matching row in another sheet if
        mapping.source_sheet points elsewhere."""
        if mapping is None:
            return None
        if not mapping.source_sheet:
            return row.get(mapping.source_column)

        other_rows = sheets_data.get(mapping.source_sheet)
        if other_rows is None:
            return None

        if mapping.source_sheet not in sheet_indexes:
            sheet_indexes[mapping.source_sheet] = _build_sheet_index(other_rows, join_key_column)

        key = row.get(join_key_column)
        if key in (None, ""):
            return None
        other_row = sheet_indexes[mapping.source_sheet].get(str(key).strip())
        return other_row.get(mapping.source_column) if other_row else None

    vms = []
    skipped = 0

    for row in rows:
        name = str(_resolve(row, name_col) or "").strip() if name_col else ""
        if not name:
            continue
        if any(name.startswith(prefix) for prefix in profile.skip_name_prefixes):
            skipped += 1
            continue

        vcpu = parse_int(_resolve(row, vcpu_col), default=1) if vcpu_col else 1
        ram_gb = parse_size_to_gb(_resolve(row, ram_col), ram_col.unit) if ram_col else 0.0
        disk_gb = parse_size_to_gb(_resolve(row, disk_col), disk_col.unit) if disk_col else 0.0
        powered_on = (
            parse_bool(_resolve(row, power_col), profile.powered_on_value)
            if power_col else True
        )
        row_site = str(_resolve(row, site_col) or site).strip() if site_col else site
        if valid_sites is not None:
            if row_site not in valid_sites:
                row_site = site
        elif row_site not in ("Primary", "DR"):
            row_site = site
        notes = str(_resolve(row, notes_col) or "").strip() if notes_col else ""
        ip_address = str(_resolve(row, ip_col) or "").strip() if ip_col else ""
        os = str(_resolve(row, os_col) or "").strip() if os_col else ""

        vms.append(VirtualMachine(
            uid=str(uuid.uuid4()),
            name=name,
            site=row_site,
            vcpu=vcpu,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            powered_on=powered_on,
            notes=notes,
            ip_address=ip_address,
            os=os,
        ))

    return vms, skipped
