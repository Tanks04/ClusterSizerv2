import pytest

from src.calculations.raid_calculator import RaidConfigError, compute_raid


def test_raid0_no_overhead():
    r = compute_raid(disk_size=4, disk_count=4, raid_level="RAID 0")
    assert r.usable_capacity == 16
    assert r.overhead_percent == 0
    assert r.warning is not None and "redundancy" in r.warning


def test_raid1_half_capacity():
    r = compute_raid(disk_size=4, disk_count=4, raid_level="RAID 1")
    assert r.usable_capacity == 8
    assert r.overhead_percent == 50


def test_raid5_n_minus_1():
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 5")
    assert r.usable_capacity == 28
    assert r.effective_disk_count == 7


def test_raid6_n_minus_2():
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 6")
    assert r.usable_capacity == 24
    assert r.effective_disk_count == 6


def test_raid10_half_capacity():
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 10")
    assert r.usable_capacity == 16


def test_raid50_nested():
    r = compute_raid(disk_size=4, disk_count=12, raid_level="RAID 50", groups=2)
    assert r.usable_capacity == 40  # (12 - 2 groups) * 4TB


def test_raid60_nested():
    r = compute_raid(disk_size=4, disk_count=16, raid_level="RAID 60", groups=2)
    assert r.usable_capacity == 48  # (16 - 2*2 groups) * 4TB


def test_hot_spares_reduce_active_disks():
    r = compute_raid(disk_size=4, disk_count=9, raid_level="RAID 5", hot_spares=1)
    assert r.usable_capacity == 28  # active=8, usable=(8-1)*4
    # raw includes the spare - it's still a physical disk purchased
    assert r.raw_capacity == 36


def test_warning_parity_plus_spinning_disk():
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 5", disk_type="SATA HDD")
    assert r.warning is not None
    assert "write penalty" in r.warning


def test_no_warning_parity_plus_flash():
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 5", disk_type="NVMe Flash")
    assert r.warning is None


def test_no_warning_raid10_plus_hdd():
    """RAID 10 has no parity, so no write-penalty warning even on HDD."""
    r = compute_raid(disk_size=4, disk_count=8, raid_level="RAID 10", disk_type="SATA HDD")
    assert r.warning is None


def test_too_few_disks_raises():
    with pytest.raises(RaidConfigError):
        compute_raid(disk_size=4, disk_count=2, raid_level="RAID 5")


def test_uneven_groups_raises():
    with pytest.raises(RaidConfigError):
        compute_raid(disk_size=4, disk_count=13, raid_level="RAID 50", groups=2)


def test_group_too_small_raises():
    # 6 disks / 3 groups = 2 per group, but RAID 50 groups need >= 3
    with pytest.raises(RaidConfigError):
        compute_raid(disk_size=4, disk_count=6, raid_level="RAID 50", groups=3)


def test_zero_disk_size_raises():
    with pytest.raises(RaidConfigError):
        compute_raid(disk_size=0, disk_count=8, raid_level="RAID 5")


def test_spares_exceeding_disk_count_raises():
    with pytest.raises(RaidConfigError):
        compute_raid(disk_size=4, disk_count=4, raid_level="RAID 0", hot_spares=4)
