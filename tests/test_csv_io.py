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
