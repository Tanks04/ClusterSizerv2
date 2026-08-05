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

    notes: str = ""

    @property
    def usable_capacity_gb(self) -> float:
        return self.usable_capacity_tb * 1024

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
        )
