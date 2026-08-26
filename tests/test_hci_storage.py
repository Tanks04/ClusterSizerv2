from src.models.server import Server
from src.calculations.hci_storage import compute_hci_raw_capacity


def _server(uid, local_disk_raw_tb=0.0):
    s = Server.create_default()
    s.uid = uid
    s.local_disk_raw_tb = local_disk_raw_tb
    return s


def test_sums_all_linked_servers():
    servers = [_server("a", 20), _server("b", 20), _server("c", 20)]
    assert compute_hci_raw_capacity(servers, ["a", "b", "c"]) == 60


def test_sums_only_the_linked_subset():
    servers = [_server("a", 20), _server("b", 20), _server("c", 20)]
    assert compute_hci_raw_capacity(servers, ["a", "b"]) == 40


def test_empty_selection_gives_zero():
    servers = [_server("a", 20)]
    assert compute_hci_raw_capacity(servers, []) == 0


def test_stale_uid_is_silently_skipped_not_an_error():
    """A uid that no longer matches any current server (e.g. that server
    was deleted from the project) must not crash - the sum just
    reflects whoever is still actually linked."""
    servers = [_server("a", 20)]
    assert compute_hci_raw_capacity(servers, ["a", "deleted-server-uid"]) == 20


def test_no_servers_at_all_gives_zero():
    assert compute_hci_raw_capacity([], ["a", "b"]) == 0


def test_servers_with_zero_local_disk_contribute_nothing():
    servers = [_server("a", 0.0), _server("b", 20.0)]
    assert compute_hci_raw_capacity(servers, ["a", "b"]) == 20
