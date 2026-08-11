from dataclasses import dataclass
import uuid


@dataclass
class Storage:
    """Represents one storage system (SAN/NAS/local) at the Primary or DR site."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    vendor: str
    model: str

    raw_capacity_tb: float
    usable_capacity_tb: float  # after RAID/erasure coding overhead

    raid_overhead_percent: float  # informational only - how much is "eaten" going from raw -> usable

    # Connectivity port inventory - same pattern as Server.nic_* and
    # NetworkSwitch.ports_*. Used on the Network tab to track free/used
    # ports for links to switches, and for direct-attach links straight
    # to a server (no switch in between) - common with FC or SAS.
    # Fully optional - if left at 0, this storage just doesn't show up in
    # the network calculations.
    ports_1g: int = 0
    ports_10g: int = 0
    ports_25g: int = 0
    ports_40g: int = 0
    ports_100g: int = 0
    ports_fc: int = 0
    ports_sas: int = 0

    notes: str = ""

    @property
    def usable_capacity_gb(self) -> float:
        return self.usable_capacity_tb * 1024

    @property
    def total_ports(self) -> int:
        return (
            self.ports_1g + self.ports_10g + self.ports_25g
            + self.ports_40g + self.ports_100g + self.ports_fc + self.ports_sas
        )

    @staticmethod
    def create_default() -> "Storage":
        return Storage(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            vendor="",
            model="",
            raw_capacity_tb=100.0,
            usable_capacity_tb=80.0,
            raid_overhead_percent=20.0,
            ports_1g=0,
            ports_10g=0,
            ports_25g=0,
            ports_40g=0,
            ports_100g=0,
            ports_fc=4,
            ports_sas=0,
        )
