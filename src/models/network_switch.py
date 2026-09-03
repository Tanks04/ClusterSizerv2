import uuid
from dataclasses import dataclass

SWITCH_TYPES = ["LAN", "SAN/FC", "Unified", "Firewall", "Load Balancer"]

# Deliberately offers every common vendor's own term rather than picking
# one canonical word - Cisco HSRP/VRRP/GLBP say "Standby", Palo Alto/
# Fortinet/most firewall HA pairs say "Passive", and MLAG/VPC/stacking
# setups have no active/standby distinction at all ("Member" - both
# forward traffic as peers). The admin picks whichever matches their
# actual setup; nothing here is auto-detected.
REDUNDANCY_ROLES = ["", "Active", "Standby", "Passive", "Member"]


@dataclass
class NetworkSwitch:
    """Represents one network device on the Network tab - a switch, or
    any other rack-mounted network appliance (firewall, load balancer)
    that shares the same shape: name/vendor/model, a port inventory by
    speed/media (same approach as Server.nic_* fields), rack/power/price,
    and notes. Not modeled as separate entity types since a firewall or
    LB genuinely doesn't need different fields for capacity-planning
    purposes here - just a different `switch_type` label. Firewall
    subscriptions (IPS/anti-malware/URL filtering, etc.) are tracked as
    Maintenance Items instead (Pricing tab) - use `applies_to` there to
    name the device, e.g. "Firewall FW-01"."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    vendor: str
    model: str
    switch_type: str  # one of SWITCH_TYPES

    ports_1g: int = 0
    ports_10g: int = 0
    ports_25g: int = 0
    ports_40g: int = 0
    ports_100g: int = 0
    ports_fc: int = 0
    ports_sas: int = 0

    # Optional - a shared tag linking two (or more) devices into the
    # same redundant pair/set, e.g. an HSRP pair, a Palo Alto Active/
    # Passive HA pair, or an MLAG/VPC stack. Any devices sharing the
    # same non-empty group get the SAME colored border on the table
    # (color auto-derived from the group name), so a redundant pair is
    # visually obvious at a glance. Works identically for switches,
    # firewalls, and load balancers - they're all NetworkSwitch here,
    # just a different switch_type. Blank = standalone, not part of
    # any group.
    redundancy_group: str = ""
    redundancy_role: str = ""  # one of REDUNDANCY_ROLES - the admin's own call, never auto-detected

    # Rack sizing - 0 = not entered, excluded from the Summary tab's rack
    # totals rather than counted as a real zero.
    rack_units: int = 0
    power_watts: float = 0.0  # nameplate/max draw from the datasheet, not "typical" - safer for circuit/PDU planning

    # Pricing (EUR) - see Server.price for the reasoning.
    price: float = 0.0

    notes: str = ""

    @property
    def total_ports(self) -> int:
        return (
            self.ports_1g + self.ports_10g + self.ports_25g
            + self.ports_40g + self.ports_100g + self.ports_fc + self.ports_sas
        )

    @staticmethod
    def create_default() -> "NetworkSwitch":
        return NetworkSwitch(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            vendor="",
            model="",
            switch_type="LAN",
            ports_1g=48,
            ports_10g=0,
            ports_25g=4,
            ports_40g=0,
            ports_100g=0,
            ports_fc=0,
            ports_sas=0,
        )


# Same 8-color palette as Cluster's DEFAULT_CLUSTER_COLORS, reused here
# for visual consistency between the two "colored grouping" features.
_REDUNDANCY_GROUP_COLORS = [
    "#e57373", "#64b5f6", "#81c784", "#ffb74d",
    "#ba68c8", "#4db6ac", "#f06292", "#a1887f",
]


def redundancy_group_color(group: str) -> str | None:
    """Deterministic color for a redundancy_group name - any two
    switches sharing the same group name always get the same color,
    with no need to store a color per switch or manage a separate
    "redundancy group" entity just to hold one. Returns None for a
    blank group (nothing to color). Uses zlib.crc32 rather than
    Python's built-in hash() - the latter is salted per-process
    (PYTHONHASHSEED), so the same group name would otherwise get a
    different color every time the app restarts."""
    if not group:
        return None
    import zlib
    index = zlib.crc32(group.encode("utf-8")) % len(_REDUNDANCY_GROUP_COLORS)
    return _REDUNDANCY_GROUP_COLORS[index]
