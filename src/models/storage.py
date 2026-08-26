from dataclasses import dataclass, field
import uuid


@dataclass
class StorageShelf:
    """One expansion shelf/tray attached to a Storage system - embedded
    directly in its parent Storage rather than a separate top-level
    entity, since a shelf never exists independently of the storage it
    expands (usually SAS-cabled straight to the head unit, or to the
    previous shelf in a chain). Only its own rack footprint matters here
    - capacity math still lives on the parent Storage's raw/usable
    fields, since RVTools-style per-shelf capacity breakdowns are well
    beyond what this tool tries to model."""
    name: str = ""
    rack_units: int = 0
    power_watts: float = 0.0
    price: float = 0.0  # a shelf is commonly its own SKU on a vendor quote - easy to forget when pricing the array


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

    # HCI (vSAN, Storage Spaces Direct, Nutanix AHV, etc.) - there's no
    # separate physical array here, the disks live IN the servers, but
    # the cluster still behaves like one shared storage pool and needs
    # to show up on this tab like any other. When True, raw_capacity_tb
    # is auto-summed from the linked servers' local_disk_raw_tb (set on
    # the Storage dialog's checkbox list) instead of being typed in
    # directly - usable_capacity_tb stays a manual entry either way,
    # since the real raw-to-usable shrinkage depends on the storage
    # policy (FTT/erasure coding) in a way this app doesn't try to model
    # exactly, the same spirit as raid_overhead_percent being
    # informational rather than authoritative for traditional arrays.
    is_hci: bool = False
    hci_server_uids: list[str] = field(default_factory=list)

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

    # Rack sizing - same pattern as Server/NetworkSwitch. 0 = not entered,
    # excluded from the Summary tab's rack totals rather than counted as
    # a real zero.
    rack_units: int = 0
    power_watts: float = 0.0  # nameplate/max draw from the datasheet, not "typical" - safer for circuit/PDU planning

    expansion_shelves: list[StorageShelf] = field(default_factory=list)

    # Pricing (EUR) - see Server.price for the reasoning. Covers the
    # head unit only - each StorageShelf has its own.
    price: float = 0.0

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

    @property
    def total_rack_units(self) -> int:
        """This storage's own U plus every attached shelf's U."""
        return self.rack_units + sum(shelf.rack_units for shelf in self.expansion_shelves)

    @property
    def total_power_watts(self) -> float:
        """This storage's own power plus every attached shelf's power."""
        return self.power_watts + sum(shelf.power_watts for shelf in self.expansion_shelves)

    @property
    def total_price(self) -> float:
        """This storage's own price plus every attached shelf's price."""
        return self.price + sum(shelf.price for shelf in self.expansion_shelves)

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
