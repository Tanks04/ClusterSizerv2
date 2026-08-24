from dataclasses import dataclass
import uuid


@dataclass
class NetworkSwitch:
    """Represents one network switch. Port inventory is by speed/media
    (same approach as Server.nic_* fields) - simple to enter, enough for
    the "free/used" calculation on the Network tab."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    vendor: str
    model: str
    switch_type: str  # "LAN" | "SAN/FC" | "Unified"

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
