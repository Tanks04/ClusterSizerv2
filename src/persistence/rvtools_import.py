"""Parses a standard RVTools export (.xlsx, multiple sheets - "Export all
to Excel" from the RVTools UI, the common case) into Server and
VirtualMachine objects.

Only two of RVTools' many sheets are used: "vHost" (one row per
physical host -> Server) and "vInfo" (one row per VM -> VirtualMachine).
RVTools doesn't have a Primary/DR concept - a single export is normally
one vCenter's inventory - so the caller supplies which site the WHOLE
file should be assigned to, same as the existing Smart Import wizard's
target-site pattern.

Column names have drifted a little across RVTools versions, so lookups
try a short list of known aliases per field rather than one exact name.
RVTools' own "MB"/"GB" labels are actually MiB/GiB (base-2) - see
https://sizing-workshop.readthedocs.io/en/latest/datacollection/rvtools/rvtools.html -
so every memory/disk value is divided by 1024, not 1000.
"""

import openpyxl

from src.models.server import Server
from src.models.virtual_machine import VirtualMachine

MIB_PER_GIB = 1024


class RVToolsImportError(ValueError):
    pass


def _normalize(header) -> str:
    return str(header or "").strip().lower()


def _find_column(headers: dict[str, int], aliases: list[str]) -> int | None:
    for alias in aliases:
        idx = headers.get(_normalize(alias))
        if idx is not None:
            return idx
    return None


def _header_index(sheet) -> dict[str, int]:
    headers = {}
    for col_idx, cell in enumerate(next(sheet.iter_rows(min_row=1, max_row=1))):
        if cell.value:
            headers[_normalize(cell.value)] = col_idx
    return headers


def _find_sheet(workbook, *candidates: str):
    for name in workbook.sheetnames:
        if _normalize(name) in {_normalize(c) for c in candidates}:
            return workbook[name]
    return None


def _cell(row, idx: int | None):
    if idx is None or idx >= len(row):
        return None
    return row[idx].value


def _looks_like_ipv4(text: str) -> bool:
    parts = text.strip().split(".")
    if len(parts) != 4:
        return False
    return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def preview_counts(path) -> tuple[int, int]:
    """Returns (vm_count, host_count) without building full objects -
    for the import dialog to show "will import X VMs and Y hosts" before
    the user commits."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        vinfo = _find_sheet(workbook, "vInfo", "tabvInfo")
        vhost = _find_sheet(workbook, "vHost", "tabvHost")
        if vinfo is None and vhost is None:
            raise RVToolsImportError(
                "This doesn't look like an RVTools export - no 'vInfo' or "
                "'vHost' sheet found. Use RVTools' File > Export all to "
                "Excel (not a single-tab export)."
            )
        vm_count = max(0, (vinfo.max_row or 1) - 1) if vinfo else 0
        host_count = max(0, (vhost.max_row or 1) - 1) if vhost else 0
        return vm_count, host_count
    finally:
        workbook.close()


def import_servers(path) -> list[Server]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = _find_sheet(workbook, "vHost", "tabvHost")
        if sheet is None:
            return []

        headers = _header_index(sheet)
        col_host = _find_column(headers, ["Host"])
        col_sockets = _find_column(headers, ["# CPU", "#CPU", "CPUs", "Sockets"])
        col_cores_per_cpu = _find_column(headers, ["Cores per CPU", "Cores p/s"])
        col_ram_mib = _find_column(headers, ["# Memory", "Memory"])
        col_cpu_model = _find_column(headers, ["CPU Model"])

        if col_host is None:
            raise RVToolsImportError(
                "The 'vHost' sheet is missing a 'Host' column - this doesn't "
                "look like a standard RVTools export."
            )

        servers = []
        for row in sheet.iter_rows(min_row=2, values_only=False):
            host_name = _cell(row, col_host)
            if not host_name:
                continue

            server = Server.create_default()
            server.name = str(host_name)
            if _looks_like_ipv4(str(host_name)):
                server.ip_address = str(host_name)
            server.sockets = int(_cell(row, col_sockets) or 1)
            server.cores_per_socket = int(_cell(row, col_cores_per_cpu) or 1)
            server.threads_per_core = 1
            server.hyperthreading_enabled = False  # RVTools doesn't reliably expose this - left for manual review after import
            ram_mib = _cell(row, col_ram_mib)
            server.ram_gb = int(float(ram_mib) / MIB_PER_GIB) if ram_mib else 0
            cpu_model = _cell(row, col_cpu_model)
            if cpu_model:
                server.cpu_model = str(cpu_model)
            server.notes = "Imported from RVTools - review Hyperthreading, vendor/model, and warranty manually."
            servers.append(server)

        return servers
    finally:
        workbook.close()


def import_vms(path) -> list[VirtualMachine]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = _find_sheet(workbook, "vInfo", "tabvInfo")
        if sheet is None:
            return []

        headers = _header_index(sheet)
        col_name = _find_column(headers, ["VM"])
        col_power = _find_column(headers, ["Powerstate"])
        col_vcpu = _find_column(headers, ["CPUs"])
        col_ram_mib = _find_column(headers, ["Memory"])
        col_disk_mib = _find_column(headers, [
            "Total disk capacity MiB", "Total disk capacity MB",
            "Provisioned MiB", "Provisioned MB", "Provisioned in MB", "In Use MiB", "In Use MB",
        ])
        col_ip = _find_column(headers, ["Primary IP Address", "IP Address"])

        if col_name is None:
            raise RVToolsImportError(
                "The 'vInfo' sheet is missing a 'VM' column - this doesn't "
                "look like a standard RVTools export."
            )

        vms = []
        for row in sheet.iter_rows(min_row=2, values_only=False):
            vm_name = _cell(row, col_name)
            if not vm_name:
                continue

            vm = VirtualMachine.create_default()
            vm.name = str(vm_name)
            vm.vcpu = int(_cell(row, col_vcpu) or 0)
            ram_mib = _cell(row, col_ram_mib)
            vm.ram_gb = int(float(ram_mib) / MIB_PER_GIB) if ram_mib else 0
            disk_mib = _cell(row, col_disk_mib)
            vm.disk_gb = int(float(disk_mib) / MIB_PER_GIB) if disk_mib else 0
            power = _cell(row, col_power)
            vm.powered_on = _normalize(power) == "poweredon" if power else True
            ip_address = _cell(row, col_ip)
            if ip_address:
                vm.ip_address = str(ip_address)
            vm.notes = "Imported from RVTools - review Workload Tier and DR Protected manually."
            vms.append(vm)

        return vms
    finally:
        workbook.close()
