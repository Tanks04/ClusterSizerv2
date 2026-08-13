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
        "threads_per_core,hyperthreading_enabled,ram_gb,cpu_frequency,warranty_expiry,"
        "nic_1g,nic_10g,nic_25g,nic_40g,nic_100g,nic_fc,nic_sas,enabled,notes\n"
    )
    row = (
        "esxi01,Primary,Dell,R750,Intel,Xeon,2.0,16.0,2.0,True,256,2.5,,0,0,0,0,0,0,0,True,\n"
    )
    csv_path.write_text(header + row, encoding="utf-8")

    servers = import_servers(csv_path)

    assert len(servers) == 1
    assert servers[0].sockets == 2
    assert servers[0].cores_per_socket == 16
    assert servers[0].threads_per_core == 2
