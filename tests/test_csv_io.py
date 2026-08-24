from src.persistence.csv_io import _bool, import_servers


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
    csv_path = tmp_path / "servers.csv"
    header = (
        "name,site,vendor,model,cpu_vendor,cpu_model,sockets,cores_per_socket,"
        "threads_per_core,hyperthreading_enabled,ram_gb,cpu_frequency,warranty_expiry,ip_address,"
        "nic_1g,nic_10g,nic_25g,nic_40g,nic_100g,nic_fc,nic_sas,enabled,notes\n"
    )
    row = (
        "esxi01,Primary,Dell,R750,Intel,Xeon,2.0,16.0,2.0,True,256,2.5,,,0,0,0,0,0,0,0,True,\n"
    )
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
