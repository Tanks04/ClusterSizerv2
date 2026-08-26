"""Computes an HCI (vSAN, Storage Spaces Direct, Nutanix AHV, etc.)
storage entity's raw capacity as the sum of its linked servers' local
disk contribution - there's no separate physical array to type a raw
capacity into directly, since the disks live in the servers.
"""

from src.models.server import Server


def compute_hci_raw_capacity(servers: list[Server], server_uids: list[str]) -> float:
    """Sums local_disk_raw_tb for whichever servers are in server_uids.
    A uid that no longer matches any current server (e.g. that server
    was deleted) is silently skipped, not an error - the sum just
    reflects whoever is still actually linked."""
    uid_set = set(server_uids)
    return sum(s.local_disk_raw_tb for s in servers if s.uid in uid_set)
