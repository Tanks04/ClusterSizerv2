import pytest
from src.persistence.csv_io import _bool, import_servers, import_vms, import_storages, import_switches, import_backup_destinations, import_vlans, import_maintenance_items, CsvSchemaError


def test_bool_none_uses_default():
    assert _bool(None, default=True) is True
    assert _bool(None, default=False) is False


def test_bool_blank_falls_back_to_default():
    assert _bool("", default=True) is True
    assert _bool("   ", default=True) is True
    assert _bool("", default=False) is False


def test_bool_falsy_tokens():
    assert _bool("false") is False
    assert _bool("0") is False
    assert _bool("no") is False
    assert _bool("FALSE") is False


def test_bool_truthy_tokens():
    assert _bool("true") is True
    assert _bool("1") is True
    assert _bool("yes") is True


def test_import_servers_accepts_float_formatted_ints(tmp_path):
    from src.persistence.csv_io import SERVER_FIELDS

    csv_path = tmp_path / "servers.csv"
    values = {
        "name": "esxi01", "site": "Primary", "vendor": "Dell", "model": "R750",
        "cpu_vendor": "Intel", "cpu_model": "Xeon",
        "sockets": "2.0", "cores_per_socket": "16.0", "threads_per_core": "2.0",
        "hyperthreading_enabled": "True", "ram_gb": "256", "cpu_frequency": "2.5",
        "enabled": "True",
    }
    header = ",".join(SERVER_FIELDS) + "\n"
    row = ",".join(values.get(f, "") for f in SERVER_FIELDS) + "\n"
    csv_path.write_text(header + row, encoding="utf-8")

    servers = import_servers(csv_path)

    assert len(servers) == 1
    assert servers[0].sockets == 2
    assert servers[0].cores_per_socket == 16
    assert servers[0].threads_per_core == 2


def test_backup_destinations_csv_round_trip(tmp_path):
    from src.models.backup_destination import BackupDestination
    from src.persistence.csv_io import import_backup_destinations, export_backup_destinations

    d1 = BackupDestination.create_default()
    d1.name = "veeam-repo-01"
    d1.destination_type = "Disk Appliance"
    d1.backup_software = "Veeam"
    d1.raw_capacity_tb = 40
    d1.dedup_ratio = 5.0
    d1.is_immutable = True

    d2 = BackupDestination.create_default()
    d2.name = "offsite-cloud"
    d2.site = "DR"
    d2.destination_type = "Offsite"
    d2.is_offsite = True

    path = tmp_path / "backup.csv"
    export_backup_destinations(path, [d1, d2])
    loaded = import_backup_destinations(path)

    assert len(loaded) == 2
    assert loaded[0].name == "veeam-repo-01"
    assert loaded[0].is_immutable is True
    assert loaded[0].is_offsite is False
    assert loaded[1].is_offsite is True
    assert loaded[0].effective_capacity_tb == 200


# ----------------------------------------------------------------------
# Backward compatibility: a CSV exported by an OLDER app version won't
# have a newer optional column yet (dr_category, hypervisor_vendor,
# location, etc.) - reported directly as a real bug, since import
# validation was checking for EVERY known field instead of just the
# small core subset that actually distinguishes one entity type's CSV
# from another's. Each test below simulates exactly that: a CSV with
# every CURRENT core column but missing one or more newer optional ones.
# ----------------------------------------------------------------------

def test_vms_csv_without_dr_category_column_still_imports(tmp_path):
    """The exact scenario reported directly."""
    path = tmp_path / "old_vms.csv"
    path.write_text(
        "name,site,vcpu,ram_gb,disk_gb,powered_on,workload_tier,ip_address,os,notes\n"
        "web-01,Primary,4,16,100,True,Standard Production,,,\n",
        encoding="utf-8",
    )

    vms = import_vms(path)

    assert len(vms) == 1
    assert vms[0].name == "web-01"
    assert vms[0].dr_category == ""


def test_servers_csv_without_newer_columns_still_imports(tmp_path):
    """Missing serial_number/bmc_ip/hypervisor_* (all added later) -
    only the foundational name/site/sockets/cores_per_socket matter."""
    path = tmp_path / "old_servers.csv"
    path.write_text(
        "name,site,vendor,model,sockets,cores_per_socket,ram_gb\n"
        "esxi-01,Primary,Dell,R750,2,32,512\n",
        encoding="utf-8",
    )

    servers = import_servers(path)

    assert len(servers) == 1
    assert servers[0].name == "esxi-01"
    assert servers[0].serial_number == ""
    assert servers[0].hypervisor_vendor == ""


def test_backup_destinations_csv_without_location_still_imports(tmp_path):
    path = tmp_path / "old_backup.csv"
    path.write_text(
        "name,site,destination_type,backup_software,raw_capacity_tb\n"
        "veeam-nas,Primary,NAS,Veeam,10\n",
        encoding="utf-8",
    )

    destinations = import_backup_destinations(path)

    assert len(destinations) == 1
    assert destinations[0].location == ""


def test_storage_csv_missing_core_column_is_still_rejected(tmp_path):
    """The wrong-file-type protection must still work - this is missing
    raw_capacity_tb/usable_capacity_tb entirely, not just a newer
    optional field."""
    path = tmp_path / "not_storage.csv"
    path.write_text("name,site,vendor\nsan01,Primary,Dell\n", encoding="utf-8")

    with pytest.raises(CsvSchemaError):
        import_storages(path)


def test_vms_csv_missing_core_column_is_still_rejected(tmp_path):
    """A genuine Servers CSV imported on the VMs tab must still fail -
    confirms the core-fields check isn't so lenient it stops catching
    real wrong-file mistakes."""
    path = tmp_path / "servers_not_vms.csv"
    path.write_text(
        "name,site,vendor,model,sockets,cores_per_socket\n"
        "esxi-01,Primary,Dell,R750,2,32\n",
        encoding="utf-8",
    )

    with pytest.raises(CsvSchemaError):
        import_vms(path)


def test_switches_csv_without_notes_still_imports(tmp_path):
    path = tmp_path / "old_switches.csv"
    path.write_text(
        "name,site,switch_type\nsw01,Primary,LAN\n",
        encoding="utf-8",
    )

    switches = import_switches(path)

    assert len(switches) == 1
    assert switches[0].notes == ""


def test_vlans_csv_without_gateway_still_imports(tmp_path):
    path = tmp_path / "old_vlans.csv"
    path.write_text(
        "name,site,network\nDMZ,Primary,192.168.10.0/24\n",
        encoding="utf-8",
    )

    vlans = import_vlans(path)

    assert len(vlans) == 1
    assert vlans[0].gateway == ""


def test_maintenance_items_csv_without_notes_still_imports(tmp_path):
    path = tmp_path / "old_maintenance.csv"
    path.write_text(
        "name,category,cost,duration_months\n"
        "Support Contract,License,1000,12\n",
        encoding="utf-8",
    )

    items = import_maintenance_items(path)

    assert len(items) == 1
    assert items[0].notes == ""
