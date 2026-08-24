from dataclasses import dataclass, field

# ClusterSizer VM fields a column can be mapped to. "name", "vcpu", "ram_gb",
# and "disk_gb" are required for a usable import - the wizard won't let you
# finish without them mapped to something.
VM_TARGET_FIELDS = [
    "name", "site", "vcpu", "ram_gb", "disk_gb", "powered_on", "notes",
]

REQUIRED_VM_FIELDS = {"name", "vcpu", "ram_gb", "disk_gb"}

# For ram_gb/disk_gb: "auto" parses embedded units like "8 GB" / "8192 MiB"
# straight out of the cell text. The rest force a fixed unit when the
# source column is a bare number (e.g. Proxmox's maxmem is bytes with no
# unit suffix at all).
SIZE_UNITS = ["auto", "B", "KB", "MB", "GB", "TB"]


@dataclass
class ColumnMapping:
    target_field: str  # one of VM_TARGET_FIELDS
    source_column: str = ""  # header text from the file, "" = unmapped
    unit: str = "auto"  # only meaningful for ram_gb / disk_gb
    source_sheet: str = ""  # "" = the primary sheet currently selected in the wizard; set to pull this one field from a DIFFERENT sheet in the same workbook (joined by the "name" field's value)


@dataclass
class ImportProfile:
    """A saved (or built-in preset) recipe for turning one export format
    into ClusterSizer VM rows: which row is the header, and which source
    column maps to which ClusterSizer field. Matched against a new file by
    comparing header signatures, so re-importing the same tool's export
    later needs zero re-mapping."""

    name: str
    header_row: int = 1  # 1-based row number where the real header lives
    mappings: list[ColumnMapping] = field(default_factory=list)
    powered_on_value: str = "Powered On"  # exact text meaning "on" in the State/Status column
    skip_name_prefixes: list[str] = field(default_factory=list)  # e.g. ["vCLS-"] to exclude system VMs
    built_in: bool = False  # built-in presets aren't shown as "delete-able" the same way
    notes: str = ""

    def mapping_for(self, target_field: str) -> ColumnMapping | None:
        return next((m for m in self.mappings if m.target_field == target_field), None)

    def is_complete(self) -> bool:
        for required in REQUIRED_VM_FIELDS:
            m = self.mapping_for(required)
            if m is None or not m.source_column:
                return False
        return True

    def header_signature(self) -> set[str]:
        """The set of source columns this profile expects to see - used to
        auto-suggest a matching profile for a newly opened file."""
        return {m.source_column for m in self.mappings if m.source_column}
