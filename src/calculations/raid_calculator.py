"""RAID capacity calculator - no Qt dependency, so it's testable on its
own. Deliberately does NOT try to cross-reference the RAID choice against
VM workload tiers elsewhere in the project - a Storage entity isn't
tied to specific VMs anywhere in the data model, so "you have a Tier-0
VM somewhere, but chose RAID 5 HERE" would often be a false alarm (that
Tier-0 VM might live on a completely different, faster array). Warnings
here are scoped to what's actually knowable from the RAID config alone:
the RAID level and the disk type going into it.
"""

from dataclasses import dataclass

RAID_LEVELS = ["RAID 0", "RAID 1", "RAID 5", "RAID 6", "RAID 10", "RAID 50", "RAID 60"]

DISK_TYPES = ["SATA HDD", "SAS HDD", "SAS SSD", "NVMe Flash"]

_SPINNING_DISK_TYPES = {"SATA HDD", "SAS HDD"}
_PARITY_LEVELS = {"RAID 5", "RAID 6", "RAID 50", "RAID 60"}

_MIN_DISKS = {
    "RAID 0": 1,
    "RAID 1": 2,
    "RAID 5": 3,
    "RAID 6": 4,
    "RAID 10": 4,
    "RAID 50": 6,
    "RAID 60": 8,
}


class RaidConfigError(ValueError):
    pass


@dataclass
class RaidResult:
    raw_capacity: float
    usable_capacity: float
    overhead_percent: float
    effective_disk_count: int
    fault_tolerance: str
    warning: str | None


def _warning_for(raid_level: str, disk_type: str) -> str | None:
    if raid_level == "RAID 0":
        return (
            "No redundancy - a single disk failure loses everything on "
            "this array. Only use for scratch/throwaway data you can "
            "afford to lose entirely."
        )
    if raid_level in _PARITY_LEVELS and disk_type in _SPINNING_DISK_TYPES:
        return (
            f"{raid_level} on spinning disks has a real write penalty and "
            "long rebuild times on large drives - if this will serve "
            "latency-sensitive workloads (e.g. databases), consider RAID 10 "
            "or flash media instead."
        )
    return None


def compute_raid(
    disk_size: float,
    disk_count: int,
    raid_level: str,
    hot_spares: int = 0,
    groups: int = 1,
    disk_type: str = "SATA HDD",
) -> RaidResult:
    if raid_level not in _MIN_DISKS:
        raise RaidConfigError(f"Unknown RAID level: {raid_level}")
    if disk_size <= 0:
        raise RaidConfigError("Disk size must be greater than 0.")
    if disk_count <= 0:
        raise RaidConfigError("Disk count must be greater than 0.")
    if hot_spares < 0 or hot_spares >= disk_count:
        raise RaidConfigError("Hot spares must be 0 or more, and fewer than the total disk count.")

    active = disk_count - hot_spares
    min_needed = _MIN_DISKS[raid_level]

    if raid_level in ("RAID 50", "RAID 60"):
        if groups < 2:
            raise RaidConfigError(f"{raid_level} needs at least 2 groups.")
        if active % groups != 0:
            raise RaidConfigError(
                f"{active} active disks doesn't divide evenly into {groups} groups."
            )
        per_group = active // groups
        group_min = 3 if raid_level == "RAID 50" else 4
        if per_group < group_min:
            raise RaidConfigError(
                f"Each {raid_level} group needs at least {group_min} disks "
                f"({active} disks / {groups} groups = {per_group} per group)."
            )
    elif active < min_needed:
        raise RaidConfigError(f"{raid_level} needs at least {min_needed} disks (have {active} after spares).")

    raw = disk_count * disk_size

    if raid_level == "RAID 0":
        usable_disks = active
        tolerance = "No redundancy - tolerates 0 disk failures"
    elif raid_level == "RAID 1":
        usable_disks = active // 2
        tolerance = "Tolerates 1 disk failure per mirrored pair"
    elif raid_level == "RAID 5":
        usable_disks = active - 1
        tolerance = "Tolerates 1 disk failure"
    elif raid_level == "RAID 6":
        usable_disks = active - 2
        tolerance = "Tolerates 2 disk failures"
    elif raid_level == "RAID 10":
        usable_disks = active // 2
        tolerance = "Tolerates 1 disk failure per mirrored pair (up to half the disks, if spread across pairs)"
    elif raid_level == "RAID 50":
        usable_disks = active - groups
        tolerance = f"Tolerates 1 disk failure per group ({groups} total, if spread across groups)"
    elif raid_level == "RAID 60":
        usable_disks = active - (2 * groups)
        tolerance = f"Tolerates 2 disk failures per group ({groups * 2} total, if spread across groups)"

    usable = usable_disks * disk_size
    overhead_percent = ((raw - usable) / raw * 100) if raw > 0 else 0.0

    return RaidResult(
        raw_capacity=raw,
        usable_capacity=usable,
        overhead_percent=overhead_percent,
        effective_disk_count=usable_disks,
        fault_tolerance=tolerance,
        warning=_warning_for(raid_level, disk_type),
    )
