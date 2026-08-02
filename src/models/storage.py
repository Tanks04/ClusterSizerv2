from dataclasses import dataclass
import uuid


@dataclass
class Storage:
    """Predstavlja jedan storage sustav (SAN/NAS/lokalni) na Primary ili DR lokaciji."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    vendor: str
    model: str

    raw_capacity_tb: float
    usable_capacity_tb: float  # nakon RAID/erasure coding overheada

    raid_overhead_percent: float  # informativno, koliko je "pojedeno" od raw -> usable

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
