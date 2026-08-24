from src.models.import_profile import ImportProfile, ColumnMapping
from src.persistence.import_engine import convert_rows, best_matching_profile


def _profile(disk_source_sheet=""):
    return ImportProfile(
        name="test",
        mappings=[
            ColumnMapping(target_field="name", source_column="VM"),
            ColumnMapping(target_field="vcpu", source_column="CPUs"),
            ColumnMapping(target_field="ram_gb", source_column="Memory", unit="MIB"),
            ColumnMapping(
                target_field="disk_gb", source_column="Capacity MiB", unit="MIB",
                source_sheet=disk_source_sheet,
            ),
        ],
    )


def test_single_sheet_import_unaffected_by_cross_sheet_support():
    """No sheets_data passed at all - must behave exactly as before the
    cross-sheet feature was added."""
    rows = [{"VM": "app-01", "CPUs": "4", "Memory": "16384", "Capacity MiB": "153600"}]
    vms, skipped = convert_rows(rows, _profile(), site="Primary")
    assert len(vms) == 1
    assert vms[0].disk_gb == 150.0


def test_cross_sheet_join_pulls_field_from_secondary_sheet():
    primary_rows = [
        {"VM": "app-01", "CPUs": "4", "Memory": "16384"},
        {"VM": "db-01", "CPUs": "8", "Memory": "65536"},
    ]
    secondary_rows = [
        {"VM": "app-01", "Capacity MiB": "153600"},
        {"VM": "db-01", "Capacity MiB": "512000"},
    ]
    profile = _profile(disk_source_sheet="vPartition")

    vms, skipped = convert_rows(
        primary_rows, profile, site="Primary",
        sheets_data={"vPartition": secondary_rows},
    )

    assert vms[0].disk_gb == 150.0
    assert vms[1].disk_gb == 500.0


def test_cross_sheet_join_falls_back_gracefully_when_key_not_found():
    primary_rows = [{"VM": "app-01", "CPUs": "4", "Memory": "16384"}]
    secondary_rows = [{"VM": "completely-different-vm", "Capacity MiB": "999999"}]
    profile = _profile(disk_source_sheet="vPartition")

    vms, skipped = convert_rows(
        primary_rows, profile, site="Primary",
        sheets_data={"vPartition": secondary_rows},
    )

    assert vms[0].disk_gb == 0.0


def test_cross_sheet_join_falls_back_gracefully_when_sheets_data_missing():
    primary_rows = [{"VM": "app-01", "CPUs": "4", "Memory": "16384"}]
    profile = _profile(disk_source_sheet="vPartition")

    vms, skipped = convert_rows(primary_rows, profile, site="Primary", sheets_data=None)

    assert vms[0].disk_gb == 0.0


def test_cross_sheet_join_falls_back_when_referenced_sheet_absent_from_data():
    """source_sheet points at a sheet that isn't in sheets_data at all
    (e.g. never actually loaded) - must not crash."""
    primary_rows = [{"VM": "app-01", "CPUs": "4", "Memory": "16384"}]
    profile = _profile(disk_source_sheet="vPartition")

    vms, skipped = convert_rows(
        primary_rows, profile, site="Primary", sheets_data={"some_other_sheet": []},
    )

    assert vms[0].disk_gb == 0.0


def test_best_matching_profile_still_works_with_source_sheet_field():
    """ColumnMapping gained source_sheet - header_signature() (used for
    auto-matching) must still work off source_column alone."""
    profile = _profile(disk_source_sheet="vPartition")
    header = ["VM", "CPUs", "Memory"]  # no "Capacity MiB" - only partial overlap
    matched = best_matching_profile(header, [profile])
    assert matched is profile
