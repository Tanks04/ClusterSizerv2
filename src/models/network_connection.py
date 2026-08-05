from dataclasses import dataclass
import uuid

# Shared speed vocabulary - used by Server.nic_*, NetworkSwitch.ports_*
# and NetworkConnection.speed, so all three sides agree on the same categories.
SPEED_OPTIONS = ["1G", "10G", "25G", "40G", "100G", "FC"]

MEDIA_OPTIONS = ["RJ45", "SFP+", "SFP28", "QSFP+", "QSFP28", "FC"]

PURPOSE_OPTIONS = ["Uplink", "Data", "Storage", "Management", "vMotion", "Other"]

# Server.nic_<x> / NetworkSwitch.ports_<x> attribute for each speed - used
# for generic capacity/usage summing without if/elif chains.
SPEED_ATTR = {
    "1G": "1g",
    "10G": "10g",
    "25G": "25g",
    "40G": "40g",
    "100G": "100g",
    "FC": "fc",
}


@dataclass
class NetworkConnection:
    """One physical link: server <-> switch. References both sides by uid
    (server_uid, switch_uid) - if the referenced device is later deleted,
    the connection stays as an "orphan" and is shown as such (not
    auto-deleted, so no data is lost by accident)."""

    uid: str

    server_uid: str
    switch_uid: str

    speed: str  # one of SPEED_OPTIONS
    media: str  # one of MEDIA_OPTIONS

    switch_port_label: str = ""  # descriptive, e.g. "Gi1/0/3", "Uplink #1" - optional
    purpose: str = "Data"  # one of PURPOSE_OPTIONS

    notes: str = ""

    @staticmethod
    def create_default() -> "NetworkConnection":
        return NetworkConnection(
            uid=str(uuid.uuid4()),
            server_uid="",
            switch_uid="",
            speed="25G",
            media="SFP28",
            purpose="Data",
        )
