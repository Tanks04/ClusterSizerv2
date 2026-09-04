import uuid
from dataclasses import dataclass, field

# Common RAID levels for the Calc button's optional Usable estimate.
# "" (no selection) skips the Usable estimate entirely - Calc only
# fills Raw in that case, exactly as before this existed.
RAID_LEVELS = ["", "RAID 0 / JBOD", "RAID 1 / RAID 10", "RAID 5", "RAID 6"]


def raid_usable_disk_count(raid_level: str, disk_count: int) -> float:
    """How many of disk_count disks' worth of capacity survive this
    RAID level's redundancy overhead - a common, rough estimate (real
    overhead varies by stripe/chunk size, spares, controller, etc.),
    the same spirit as raid_overhead_percent being informational
    rather than an authoritative computation."""
    if raid_level == "RAID 0 / JBOD":
        return disk_count
    if raid_level == "RAID 1 / RAID 10":
        return disk_count / 2
    if raid_level == "RAID 5":
        return max(0, disk_count - 1)
    if raid_level == "RAID 6":
        return max(0, disk_count - 2)
    return 0  # "" or anything unrecognized - no estimate offered


# FTT (Failures To Tolerate) levels for HCI/vSAN-style storage - the
# Calc button's optional Usable estimate when is_hci is checked
# (mirrors raid_usable_disk_count for traditional arrays, just
# expressed as an overhead FACTOR on raw capacity rather than a disk-
# count formula, since HCI's raw already comes from linked servers
# rather than a manual disk count).
FTT_LEVELS = [
    "", "FTT=0 (No tolerance)", "FTT=1 Mirroring", "FTT=1 Erasure Coding",
    "FTT=2 Mirroring", "FTT=2 Erasure Coding",
]


def ftt_usable_factor(ftt_level: str) -> float:
    """Fraction of raw capacity that survives this FTT level's
    redundancy overhead - a common, rough estimate (real overhead
    varies by cluster size, object policy, slack space reserved by
    the platform, etc.), same spirit as raid_usable_disk_count."""
    factors = {
        "FTT=0 (No tolerance)": 1.0,
        "FTT=1 Mirroring": 0.5,
        "FTT=1 Erasure Coding": 0.75,  # RAID5-like, needs 4+ nodes
        "FTT=2 Mirroring": 1 / 3,
        "FTT=2 Erasure Coding": 2 / 3,  # RAID6-like, needs 6+ nodes
    }
    return factors.get(ftt_level, 0.0)


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
class StoragePool:
    """One carved-out slice of a Storage array's disks - a real array
    commonly splits its physical disks into several pools (e.g. a
    fast SSD tier and a bulk SATA tier, or one pool per set of servers
    it's zoned to), each with its own capacity. Embedded in its parent
    Storage the same way StorageShelf is, since a pool never exists
    independently of the array it's carved from. server_uids records
    which servers this pool is presented to (zoning/masking) - a VM
    can optionally reference a specific pool via storage_pool_uid,
    narrower than just picking the Storage array as a whole. Purely
    additive: a Storage with an empty pools list behaves exactly as
    before this existed - its own raw/usable capacity is still the
    array-wide total."""
    uid: str
    name: str = ""
    raw_capacity_tb: float = 0.0
    usable_capacity_tb: float = 0.0
    server_uids: list[str] = field(default_factory=list)
    notes: str = ""

    # What this pool is actually built from - unlike Storage's own
    # disk_count/disk_size_tb/raid_level (which describe the array as
    # ONE undivided whole), a pool needs its own copy since different
    # pools on the same array commonly use different disk types
    # entirely (e.g. a 7x15TB NVMe pool alongside a 10x SAS-SSD pool).
    # Filled in via the RAID Calculator (opened from the pool's own
    # dialog) - reported directly as important to keep, since "how
    # many disks, what size" got lost once a RAID result was applied
    # and only the resulting raw/usable capacity survived. Editing
    # this pool's disks later (e.g. an admin buying 4 more 15TB disks
    # to expand it) starts from these saved values instead of from
    # scratch.
    disk_count: int = 0
    disk_size_tb: float = 0.0
    raid_level: str = ""

    # PCI passthrough - the opposite assignment direction from
    # server_uids above. A normal pool is zoned to hosts, which the
    # hypervisor then presents to VMs as shared datastore capacity; a
    # passthrough pool bypasses that entirely, wired directly to ONE
    # VM (common for security appliances or storage-heavy workloads
    # needing raw disk access) - the hosts/cluster never see it at
    # all. server_uids is meaningless when this is set.
    is_passthrough: bool = False
    passthrough_vm_uid: str = ""


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

    # Which servers/hosts are zoned to see this WHOLE array - the same
    # idea as StoragePool.server_uids, one level coarser (the array as
    # a whole rather than a specific pool carved from it). Meaningful
    # for an array that hasn't been split into pools at all; once
    # pools exist, per-pool zoning is normally more precise, but this
    # stays available as a simpler default. Bulk-assignable from the
    # Servers tab - can auto-populate from a Cluster's current member
    # servers as a starting point, then be edited per-server afterward.
    server_uids: list[str] = field(default_factory=list)

    # Optional calculator inputs - when both are set, the GUI can fill
    # raw_capacity_tb with their product (disk_count * disk_size_tb) as
    # a convenience, for both traditional arrays and HCI alike.
    # raw_capacity_tb stays the real, stored, independently-editable
    # value (for HCI, it's normally auto-summed from linked servers
    # instead - these calculator fields are for the non-HCI case, or
    # for double-checking an HCI number by hand).
    disk_count: int = 0
    disk_size_tb: float = 0.0

    # Optional - when set to something other than "", the Calc button
    # ALSO fills usable_capacity_tb with a rough estimate based on this
    # RAID level's common overhead (e.g. RAID5 = disk_count - 1 disks
    # usable). usable_capacity_tb stays the real, stored, independently
    # -editable value either way - this is a starting estimate, not an
    # authoritative computation, same spirit as raid_overhead_percent
    # being informational rather than binding.
    raid_level: str = ""

    # Same idea as raid_level, but for HCI (is_hci checked) - FTT
    # (Failures To Tolerate) level, applied as a factor on the auto-
    # summed raw_capacity_tb to estimate Usable when the Calc button
    # is clicked. Also just a starting estimate, independently editable.
    ftt_level: str = ""

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

    # Optional carved-out slices of this array's disks - empty by
    # default, meaning the whole array is treated as one pool (this
    # Storage's own raw/usable fields), exactly as before this existed.
    pools: list[StoragePool] = field(default_factory=list)

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
