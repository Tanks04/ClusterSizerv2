from dataclasses import dataclass
import uuid

# Shared speed vocabulary - used by Server.nic_*, NetworkSwitch.ports_*,
# Storage.ports_*, and NetworkConnection.speed, so all sides agree on the
# same categories.
SPEED_OPTIONS = ["1G", "10G", "25G", "40G", "100G", "FC", "SAS"]

MEDIA_OPTIONS = ["RJ45", "SFP+", "SFP28", "QSFP+", "QSFP28", "FC", "SAS"]

PURPOSE_OPTIONS = ["Uplink", "Data", "Storage", "Management", "vMotion", "Other"]

# Server.nic_<x> / NetworkSwitch.ports_<x> / Storage.ports_<x> attribute
# for each speed - used for generic capacity/usage summing without
# if/elif chains.
SPEED_ATTR = {
    "1G": "1g",
    "10G": "10g",
    "25G": "25g",
    "40G": "40g",
    "100G": "100g",
    "FC": "fc",
    "SAS": "sas",
}

# The four kinds of link a NetworkConnection can represent, based on
# which uid fields are populated. Server<->Switch is the original/most
# common case; Storage<->Switch and Server<->Storage (direct-attach, no
# switch - common with FC or SAS HBAs wired straight to an array) were
# added later without changing the existing field names, so old saved
# .clsz files with only server_uid/switch_uid keep working unchanged.
# Switch<->Switch (switch_uid + switch_b_uid) was added later still -
# for an inter-switch uplink, or the physical/logical link between a
# redundant pair (HSRP/VRRP, an HA firewall pair, an MLAG/VPC stack -
# "Firewall" and "Load Balancer" are just switch_type values on the
# same NetworkSwitch entity, so this works for those too).
KIND_SERVER_SWITCH = "Server \u2194 Switch"
KIND_STORAGE_SWITCH = "Storage \u2194 Switch"
KIND_SERVER_STORAGE = "Server \u2194 Storage (direct)"
KIND_SWITCH_SWITCH = "Switch \u2194 Switch"


@dataclass
class NetworkConnection:
    """One physical link between two of {Server, Switch, Storage}.
    References each side by uid - if a referenced device is later
    deleted, the connection stays as an "orphan" and is shown as such
    (not auto-deleted, so no data is lost by accident).

    Exactly two of (server_uid, switch_uid, storage_uid, switch_b_uid)
    should be non-empty - which two determines the connection's kind
    (see connection_kind property and the KIND_* constants above)."""

    uid: str

    server_uid: str
    switch_uid: str

    speed: str  # one of SPEED_OPTIONS
    media: str  # one of MEDIA_OPTIONS

    switch_port_label: str = ""  # descriptive, e.g. "Gi1/0/3", "Uplink #1" - optional
    purpose: str = "Data"  # one of PURPOSE_OPTIONS

    storage_uid: str = ""  # non-empty for Storage<->Switch or Server<->Storage links
    switch_b_uid: str = ""  # non-empty for a Switch<->Switch link (uplink, or a redundant pair's own interconnect)

    # A proprietary/dedicated cable (e.g. Cisco StackWise, a firewall
    # HA-sync port, a dedicated cluster heartbeat link) that does NOT
    # consume one of the device's declared 1G/10G/etc ports - excluded
    # from the port-usage/over-commit counting on the Network tab, even
    # though Speed/Media above can still be filled in for reference.
    dedicated_link: bool = False

    notes: str = ""

    @property
    def connection_kind(self) -> str:
        if self.switch_uid and self.switch_b_uid:
            return KIND_SWITCH_SWITCH
        if self.storage_uid and self.switch_uid:
            return KIND_STORAGE_SWITCH
        if self.storage_uid and self.server_uid:
            return KIND_SERVER_STORAGE
        return KIND_SERVER_SWITCH

    @staticmethod
    def create_default() -> "NetworkConnection":
        return NetworkConnection(
            uid=str(uuid.uuid4()),
            server_uid="",
            switch_uid="",
            speed="25G",
            media="SFP28",
            purpose="Data",
            storage_uid="",
            switch_b_uid="",
            dedicated_link=False,
        )
