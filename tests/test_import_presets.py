"""Regression tests for the built-in import presets, and for the
sheet-switching scenario that motivated the "always rebuild the mapping
UI, don't rely on setCurrentIndex() firing a signal" fix in
import_wizard_dialog.py - see that fix's comment for the full mechanism.
"""

from src.persistence import import_presets
from src.persistence.import_engine import best_matching_profile, convert_rows


def _rvtools_preset():
    return next(p for p in import_presets.PRESETS if p.name == "RVTools (vInfo tab)")


def test_rvtools_preset_disk_column_is_total_disk_capacity_not_provisioned():
    """Pins a real bug: the preset used to point at "Provisioned MB",
    which doesn't exist in real RVTools exports (the real column is
    "Total disk capacity MiB") - Provisioned MiB DOES exist but measures
    something different (datastore space reserved, including thin-
    provisioning/snapshot overhead) and reads far higher than a VM's
    actual configured disk size."""
    preset = _rvtools_preset()
    disk_mapping = preset.mapping_for("disk_gb")
    assert disk_mapping.source_column == "Total disk capacity MiB"
    assert disk_mapping.unit == "MIB"


def test_rvtools_vinfo_and_vcpu_headers_both_match_the_same_preset():
    """This is the exact condition that caused the sheet-switching bug:
    RVTools' vInfo and vCPU sheets overlap enough (VM, Powerstate, CPUs,
    "OS according to the configuration file") that BOTH best-match the
    same built-in preset. In the dialog, this meant QComboBox.
    setCurrentIndex() was called with the SAME index on both sheets - a
    no-op that fires no signal in Qt - silently skipping the mapping UI
    rebuild and leaving it showing the previous sheet's columns. The fix
    calls the rebuild directly instead of relying on the signal; this
    test pins the underlying data condition so a future preset change
    that removes the overlap doesn't silently invalidate the scenario."""
    vinfo_header = [
        "VM", "Powerstate", "Template", "CPUs", "Memory",
        "Total disk capacity MiB", "OS according to the configuration file",
    ]
    vcpu_header = [
        "VM", "Powerstate", "Template", "CPUs", "Sockets", "Cores p/s",
        "OS according to the configuration file", "Datacenter", "Cluster", "Host",
    ]

    vinfo_match = best_matching_profile(vinfo_header, import_presets.PRESETS)
    vcpu_match = best_matching_profile(vcpu_header, import_presets.PRESETS)

    assert vinfo_match is not None
    assert vcpu_match is not None
    assert vinfo_match.name == vcpu_match.name == "RVTools (vInfo tab)"


def test_rvtools_preset_converts_realistic_row_to_expected_gb():
    preset = _rvtools_preset()
    row = {
        "VM": "app-01",
        "Powerstate": "poweredOn",
        "CPUs": "4",
        "Memory": "16384",  # MiB -> 16 GB
        "Total disk capacity MiB": "153600",  # MiB -> 150 GB
        "OS according to the configuration file": "Other Linux",
    }
    vms, skipped = convert_rows([row], preset, site="Primary")
    assert len(vms) == 1
    assert skipped == 0
    vm = vms[0]
    assert vm.name == "app-01"
    assert vm.vcpu == 4
    assert vm.ram_gb == 16.0
    assert vm.disk_gb == 150.0
    assert vm.powered_on is True
