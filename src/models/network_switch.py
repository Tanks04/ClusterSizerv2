from dataclasses import dataclass
import uuid

SWITCH_TYPES = ["LAN", "SAN/FC", "Unified", "Firewall", "Load Balancer"]


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
