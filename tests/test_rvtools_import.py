import openpyxl
import pytest

from src.persistence import rvtools_import


def _write_sample_export(path, include_vhost=True, include_vinfo=True):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    if include_vhost:
        vhost = wb.create_sheet("vHost")
        vhost.append(["Host", "Datacenter", "Cluster", "# CPU", "Cores per CPU", "# Cores", "# Memory", "CPU Model"])
        vhost.append(["esxi-01.lab.local", "DC1", "Cluster1", 2, 24, 48, 524288, "Intel Xeon Gold 6338"])
        vhost.append(["esxi-02.lab.local", "DC1", "Cluster1", 2, 24, 48, 524288, "Intel Xeon Gold 6338"])

    if include_vinfo:
        vinfo = wb.create_sheet("vInfo")
        vinfo.append(["VM", "Powerstate", "Template", "CPUs", "Memory", "Provisioned MiB", "Host", "Cluster", "Datacenter"])
        vinfo.append(["app-01", "poweredOn", False, 4, 16384, 153600, "esxi-01.lab.local", "Cluster1", "DC1"])
        vinfo.append(["db-01", "poweredOn", False, 8, 65536, 512000, "esxi-01.lab.local", "Cluster1", "DC1"])
        vinfo.append(["old-test", "poweredOff", False, 2, 4096, 51200, "esxi-02.lab.local", "Cluster1", "DC1"])

    wb.save(path)


def test_preview_counts(tmp_path):
    path = tmp_path / "export.xlsx"
    _write_sample_export(path)
    vm_count, host_count = rvtools_import.preview_counts(path)
    assert vm_count == 3
    assert host_count == 2


def test_import_servers_maps_fields_and_converts_mib_to_gib(tmp_path):
    path = tmp_path / "export.xlsx"
    _write_sample_export(path)
    servers = rvtools_import.import_servers(path)

    assert len(servers) == 2
    assert servers[0].name == "esxi-01.lab.local"
    assert servers[0].sockets == 2
    assert servers[0].cores_per_socket == 24
    assert servers[0].ram_gb == 512  # 524288 MiB / 1024
    assert servers[0].cpu_model == "Intel Xeon Gold 6338"
    assert servers[0].hyperthreading_enabled is False  # deliberately conservative default


def test_import_vms_maps_fields_and_converts_mib_to_gib(tmp_path):
    path = tmp_path / "export.xlsx"
    _write_sample_export(path)
    vms = rvtools_import.import_vms(path)

    assert len(vms) == 3
    assert vms[0].name == "app-01"
    assert vms[0].vcpu == 4
    assert vms[0].ram_gb == 16
    assert vms[0].disk_gb == 150
    assert vms[0].powered_on is True
    assert vms[2].powered_on is False  # old-test is poweredOff


def test_non_rvtools_file_raises_clear_error(tmp_path):
    path = tmp_path / "unrelated.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["Name", "Age"])
    wb.active.append(["Bob", 30])
    wb.save(path)

    with pytest.raises(rvtools_import.RVToolsImportError):
        rvtools_import.preview_counts(path)


def test_missing_vinfo_sheet_returns_zero_vms(tmp_path):
    path = tmp_path / "host_only.xlsx"
    _write_sample_export(path, include_vinfo=False)

    servers = rvtools_import.import_servers(path)
    vms = rvtools_import.import_vms(path)
    assert len(servers) == 2
    assert len(vms) == 0


def test_missing_vhost_sheet_returns_zero_servers(tmp_path):
    path = tmp_path / "vms_only.xlsx"
    _write_sample_export(path, include_vhost=False)

    servers = rvtools_import.import_servers(path)
    vms = rvtools_import.import_vms(path)
    assert len(servers) == 0
    assert len(vms) == 3


def test_import_servers_detects_ip_address_when_host_is_an_ip(tmp_path):
    """RVTools' vHost sheet sometimes identifies hosts by IP directly -
    when it does, populate ip_address too, not just name."""
    path = tmp_path / "export.xlsx"
    _write_sample_export(path)
    servers = rvtools_import.import_servers(path)
    assert servers[0].ip_address == "esxi-01.lab.local" or servers[0].ip_address == ""
    # the synthetic fixture uses hostnames, not IPs - confirm hostname does NOT get miscategorized as an IP
    assert servers[0].ip_address == ""


def test_import_servers_detects_ip_address_from_real_ip_host(tmp_path):
    path = tmp_path / "export_ip.xlsx"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    vhost = wb.create_sheet("vHost")
    vhost.append(["Host", "# CPU", "Cores per CPU", "# Memory"])
    vhost.append(["10.88.1.10", 2, 24, 524288])
    wb.save(path)

    servers = rvtools_import.import_servers(path)
    assert servers[0].name == "10.88.1.10"
    assert servers[0].ip_address == "10.88.1.10"


def test_import_vms_populates_ip_address_when_present(tmp_path):
    path = tmp_path / "export_vm_ip.xlsx"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    vinfo = wb.create_sheet("vInfo")
    vinfo.append(["VM", "Powerstate", "CPUs", "Memory", "Total disk capacity MiB", "Primary IP Address"])
    vinfo.append(["app-01", "poweredOn", 4, 16384, 153600, "10.20.1.15"])
    vinfo.append(["app-02", "poweredOn", 2, 8192, 51200, ""])
    wb.save(path)

    vms = rvtools_import.import_vms(path)

    assert vms[0].ip_address == "10.20.1.15"
    assert vms[1].ip_address == ""
