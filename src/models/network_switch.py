from dataclasses import dataclass
import uuid


@dataclass
class NetworkSwitch:
    """Predstavlja jedan mrežni switch. Port inventar je po brzini/mediju
    (isti pristup kao Server.nic_* polja) - jednostavno za unos, dovoljno
    za "slobodno/zauzeto" izračun na Network tabu."""

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

    notes: str = ""

    @property
    def total_ports(self) -> int:
        return (
            self.ports_1g + self.ports_10g + self.ports_25g
            + self.ports_40g + self.ports_100g + self.ports_fc
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
        )
