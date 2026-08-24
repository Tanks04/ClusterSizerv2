"""Built-in ImportProfile presets for common export tools - starting
points, not guarantees (export formats drift between tool versions, which
is exactly why the wizard lets you adjust and re-save as your own)."""

from src.models.import_profile import ImportProfile, ColumnMapping

PRESETS: list[ImportProfile] = [
    ImportProfile(
        name="VMware vCenter (VMs for Cluster export) - unverified sample",
        header_row=1,
        built_in=True,
        powered_on_value="Powered On",
        skip_name_prefixes=["vCLS-", "Status\""],
        notes=(
            "Built from one real-world file, but that file had been manually "
            "edited by someone before we saw it - so this ISN'T confirmed to "
            "match a genuine, untouched vCenter export. Treat it as a "
            "starting point: if the column mapping below doesn't match your "
            "file, that's expected, just remap and save your own profile. "
            "The 'Status\"' skip-prefix is a leftover from that edited file, "
            "not a known vCenter quirk - harmless to leave in (no real VM "
            "would be named exactly that), safe to remove if you want."
        ),
        mappings=[
            ColumnMapping(target_field="name", source_column="Name"),
            ColumnMapping(target_field="vcpu", source_column="CPUs"),
            ColumnMapping(target_field="ram_gb", source_column="Memory Size", unit="auto"),
            ColumnMapping(target_field="disk_gb", source_column="Provisioned Space", unit="auto"),
            ColumnMapping(target_field="powered_on", source_column="State"),
            ColumnMapping(target_field="notes", source_column="Guest OS"),
        ],
    ),
    ImportProfile(
        name="RVTools (vInfo tab)",
        header_row=1,
        built_in=True,
        powered_on_value="poweredOn",
        skip_name_prefixes=["vCLS-"],
        notes=(
            "Export the vInfo tab as CSV/XLSX from RVTools. Disk maps to "
            "'Total disk capacity MiB' (the VM's configured vDisk size) "
            "rather than 'Provisioned MiB' (datastore space actually "
            "reserved, which includes thin-provisioning/snapshot overhead "
            "and runs noticeably higher) - verified against a real export."
        ),
        mappings=[
            ColumnMapping(target_field="name", source_column="VM"),
            ColumnMapping(target_field="vcpu", source_column="CPUs"),
            ColumnMapping(target_field="ram_gb", source_column="Memory", unit="MIB"),
            ColumnMapping(target_field="disk_gb", source_column="Total disk capacity MiB", unit="MIB"),
            ColumnMapping(target_field="powered_on", source_column="Powerstate"),
            ColumnMapping(target_field="notes", source_column="OS according to the configuration file"),
        ],
    ),
    ImportProfile(
        name="Nutanix Prism (VM table export)",
        header_row=1,
        built_in=True,
        powered_on_value="On",
        skip_name_prefixes=[],
        notes="Prism Central/Element VM list export.",
        mappings=[
            ColumnMapping(target_field="name", source_column="VM Name"),
            ColumnMapping(target_field="vcpu", source_column="vCPUs"),
            ColumnMapping(target_field="ram_gb", source_column="Memory", unit="auto"),
            ColumnMapping(target_field="disk_gb", source_column="Storage", unit="auto"),
            ColumnMapping(target_field="powered_on", source_column="Power State"),
        ],
    ),
    ImportProfile(
        name="Proxmox VE (pvesh cluster/resources, type=vm, JSON)",
        header_row=1,
        built_in=True,
        powered_on_value="running",
        skip_name_prefixes=[],
        notes="Generate with: pvesh get /cluster/resources --type vm --output-format json",
        mappings=[
            ColumnMapping(target_field="name", source_column="name"),
            ColumnMapping(target_field="vcpu", source_column="maxcpu"),
            ColumnMapping(target_field="ram_gb", source_column="maxmem", unit="B"),
            ColumnMapping(target_field="disk_gb", source_column="maxdisk", unit="B"),
            ColumnMapping(target_field="powered_on", source_column="status"),
        ],
    ),
]
