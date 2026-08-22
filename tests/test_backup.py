from src.models.backup_destination import BackupDestination
from src.calculations.backup import compute_compliance


def _dest(dtype="NAS", offsite=False, immutable=False, raw=10.0, dedup=1.0):
    d = BackupDestination.create_default()
    d.destination_type = dtype
    d.is_offsite = offsite
    d.is_immutable = immutable
    d.raw_capacity_tb = raw
    d.dedup_ratio = dedup
    return d


def test_effective_capacity_applies_dedup_ratio():
    d = _dest(raw=10.0, dedup=5.0)
    assert d.effective_capacity_tb == 50.0


def test_empty_list_fails_everything():
    check = compute_compliance([])
    assert check.total_copies == 1  # just production, no backups
    assert not check.meets_3_2_1
    assert not check.meets_3_2_1_1
    assert len(check.missing) == 3  # copies, media diversity, offsite


def test_single_destination_not_enough_copies():
    check = compute_compliance([_dest()])
    assert check.total_copies == 2  # 1 backup + 1 production, still < 3
    assert not check.meets_3_2_1


def test_two_same_type_no_offsite_fails_media_and_offsite():
    check = compute_compliance([_dest("NAS"), _dest("NAS")])
    assert check.total_copies == 3  # copies requirement met
    assert check.distinct_media_types == 1  # but media diversity is not
    assert not check.meets_3_2_1
    assert "media" in check.missing[0] or any("media" in m for m in check.missing)


def test_two_different_types_with_offsite_meets_3_2_1():
    check = compute_compliance([_dest("NAS"), _dest("Offsite", offsite=True)])
    assert check.meets_3_2_1
    assert not check.meets_3_2_1_1  # no immutable copy yet


def test_full_3_2_1_1_with_immutable():
    check = compute_compliance([
        _dest("NAS"),
        _dest("Offsite", offsite=True, immutable=True),
    ])
    assert check.meets_3_2_1
    assert check.meets_3_2_1_1
    assert check.missing == []


def test_missing_lists_exact_gaps():
    check = compute_compliance([_dest("NAS"), _dest("Offsite", offsite=True)])
    assert any("immutable" in m for m in check.missing)


def test_offsite_and_immutable_can_be_the_same_destination():
    """A single destination can carry both flags at once - the checks are
    independent, not mutually exclusive."""
    check = compute_compliance([
        _dest("NAS"),
        _dest("Offsite", offsite=True, immutable=True),
    ])
    assert check.has_offsite
    assert check.has_immutable
