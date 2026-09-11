import uuid
from dataclasses import dataclass

# Shared speed vocabulary - used by Server.nic_*, NetworkSwitch.ports_*,
# Storage.ports_*, and NetworkConnection.speed, so all sides agree on the
# same categories.
SPEED_OPTIONS = ["1G", "10G", "25G", "40G", "100G", "FC", "SAS"]

# Cascading classification for a connection's physical media - Speed ->
# Connector (form factor) -> Detail (fiber/copper/DAC/AOC or cable
# category). Each level's valid options depend on the level above, so
# a physically-nonsensical combination (e.g. 1G on an SFP+, which is
# actually a 10G+ form factor - SFP is 1G's real partner) can't be
# selected in the first place. FC has no Connector step of its own -
# the speed already implies the connector, so its options go straight
# from Speed to Detail (shortwave vs longwave). SAS has neither -  it's
# specific enough on its own. A connection with no informative Detail
# for its connector simply has none.
SPEED_TO_CONNECTORS: dict[str, list[str]] = {
    "1G": ["RJ45", "SFP"],
    "10G": ["RJ45", "SFP+"],
    "25G": ["SFP28"],
    "40G": ["QSFP+"],
    "100G": ["QSFP28"],
    "FC": [],
    "SAS": [],
}

CONNECTOR_TO_DETAILS: dict[str, list[str]] = {
    "RJ45": ["Cat5e", "Cat6", "Cat6a", "Cat7"],
    "SFP": ["Copper", "Fiber"],
    "SFP+": ["SR (Fiber)", "LR (Fiber)", "DAC", "AOC"],
    "SFP28": ["SR (Fiber)", "LR (Fiber)", "DAC", "AOC"],
    "QSFP+": ["SR4 (Fiber)", "LR4 (Fiber)", "DAC", "AOC"],
    "QSFP28": ["SR4 (Fiber)", "LR4 (Fiber)", "DAC", "AOC"],
}

# FC skips the Connector step entirely - these are its Detail options
# directly off Speed.
FC_DETAILS = ["SW (Shortwave/Multimode)", "LW (Longwave/Singlemode)"]


def connection_media_summary(connection: "NetworkConnection") -> str:
    """Readable one-line summary of a connection's physical media -
    combines the Connector/Detail cascade with the optional exact
    part number, and falls back gracefully for a connection saved
    before this cascade existed (old flat values live on in `media`
    alone). Shared by the connections table and the Word report so
    this logic exists in exactly one place."""
    classification = " ".join(p for p in (connection.connector, connection.media_detail) if p)
    if connection.media and classification:
        return f"{classification} ({connection.media})"
    if connection.media:
        return connection.media
    if classification:
        return classification
    return "-"


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
    media: str = ""  # optional exact part number/SKU, e.g. "GLC-T" - the structured classification is connector/media_detail below

    # Cascading physical classification - each level's valid options
    # depend on the level above (see SPEED_TO_CONNECTORS/
    # CONNECTOR_TO_DETAILS/FC_DETAILS). Both optional and independent
    # of the free-text media/cable_length fields - fill in as much
    # precision as actually matters for ordering/documentation.
    connector: str = ""  # form factor, e.g. "SFP+" - empty for FC/SAS, which have none of their own
    media_detail: str = ""  # e.g. "DAC", "SR (Fiber)", "SW (Shortwave/Multimode)" for FC
    cable_length: str = ""  # free text, e.g. "3m" - continuous, doesn't fit a dropdown

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

    # Excludes this specific link from port-usage counting without
    # deleting it - for simulating "this one cable/uplink is down for
    # maintenance" without disabling the whole switch (which would
    # affect every other port on it too).
    enabled: bool = True

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
            connector="SFP28",
            purpose="Data",
            storage_uid="",
            switch_b_uid="",
            dedicated_link=False,
        )
