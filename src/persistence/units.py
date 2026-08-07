"""Size/number parsing helpers shared by the generic import wizard and any
vendor-specific converter scripts."""

import re

SIZE_UNITS_TO_GB = {
    "B": 1 / (1024 ** 3),
    "KB": 1 / (1024 ** 2),
    "KIB": 1 / (1024 ** 2),
    "MB": 1 / 1024,
    "MIB": 1 / 1024,
    "GB": 1.0,
    "GIB": 1.0,
    "TB": 1024.0,
    "TIB": 1024.0,
}


def parse_size_to_gb(value, unit: str = "auto") -> float:
    """Converts a cell value to GB (float).

    unit="auto": the cell text itself carries the unit, e.g. '826.9 GB',
    '4.32 TiB', '160 MB', '1,009.86 GB', '8192' (bare number - MiB is
    assumed for a bare number with no suffix, since that's the common case
    for hypervisor "memory in MiB" fields... but if in doubt, don't use
    auto, pick the fixed unit the source tool actually uses).

    unit="B"/"KB"/"MB"/"GB"/"TB": the cell is a bare number already in that
    unit (e.g. Proxmox's maxmem/maxdisk fields are raw bytes with no
    suffix at all).
    """
    if value is None or value == "":
        return 0.0

    text = str(value).strip().replace(",", "")

    if unit != "auto":
        try:
            factor = SIZE_UNITS_TO_GB[unit.upper()]
        except KeyError:
            return 0.0
        try:
            return round(float(text) * factor, 2)
        except ValueError:
            return 0.0

    match = re.match(r"^([\d.]+)\s*([A-Za-z]*)$", text)
    if not match:
        return 0.0
    number, suffix = match.groups()
    suffix = suffix.upper() or "MB"  # bare number with no unit: assume MiB (common hypervisor default)
    factor = SIZE_UNITS_TO_GB.get(suffix)
    if factor is None:
        return 0.0
    try:
        return round(float(number) * factor, 2)
    except ValueError:
        return 0.0


def parse_int(value, default: int = 0) -> int:
    try:
        return int(round(float(str(value).strip().replace(",", ""))))
    except (TypeError, ValueError):
        return default


def parse_bool(value, true_text: str) -> bool:
    """True if `value` case-insensitively matches `true_text` (e.g. the
    profile's configured powered_on_value, like 'Powered On' or 'running')."""
    return str(value or "").strip().lower() == true_text.strip().lower()
