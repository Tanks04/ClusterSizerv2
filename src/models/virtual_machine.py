from dataclasses import dataclass
import uuid

from src.models.workload_tier import DEFAULT_WORKLOAD_TIER


@dataclass
class VirtualMachine:
    """Represents one virtual machine that counts toward cluster capacity.

    dr_protected + dr_* fields exist because VMs are often NOT replicated
    1:1 to DR (e.g. replicated with fewer resources, or not replicated at
    all). When dr_protected=False, the VM is not counted in DR failover
    demand - it only consumes resources at its home (site) location.

    workload_tier feeds the Cluster Preparation sizing wizard (see
    src/calculations/cluster_preparation.py) - it does NOT affect the
    existing oversubscription ratio math on Summary/VMs/Reports, which
    stays a flat, project-wide vCPU:pCPU ratio. These are two different,
    complementary calculations: the existing ratio answers "given the
    servers I HAVE, is this safe", while Cluster Preparation answers
    "given the VMs I NEED to run, how many servers should I buy" - using
    a PER-VM oversubscription-ratio tier (src/models/workload_tier.py),
    since a single project-wide ratio is too blunt when sizing new
    hardware for a mixed workload from scratch.
    """

    uid: str
    name: str
    site: str  # "Primary" | "DR" - which cluster the VM currently "lives" on

    vcpu: int
    ram_gb: float
    disk_gb: float

    powered_on: bool = True

    dr_protected: bool = False  # is this VM replicated to DR (failover)?
    dr_vcpu: int = 0            # DR footprint - can be smaller than vcpu
    dr_ram_gb: float = 0.0
    dr_disk_gb: float = 0.0

    workload_tier: str = DEFAULT_WORKLOAD_TIER

    ip_address: str = ""  # guest OS IP, free text (not validated - IPv4/IPv6/hostname all fine)

    os: str = ""  # e.g. "Ubuntu Linux (64-bit)" - free text, whatever the source system reports

    vlan_uid: str = ""  # optional reference to a Vlan.uid - independent of ip_address, never required together

    notes: str = ""

    @property
    def effective_dr_vcpu(self) -> int:
        return self.dr_vcpu if self.dr_protected else 0

    @property
    def effective_dr_ram_gb(self) -> float:
        return self.dr_ram_gb if self.dr_protected else 0.0

    @property
    def effective_dr_disk_gb(self) -> float:
        return self.dr_disk_gb if self.dr_protected else 0.0

    @staticmethod
    def create_default() -> "VirtualMachine":
        return VirtualMachine(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            vcpu=2,
            ram_gb=8.0,
            disk_gb=100.0,
            dr_protected=False,
            dr_vcpu=2,
            dr_ram_gb=8.0,
            dr_disk_gb=100.0,
            workload_tier=DEFAULT_WORKLOAD_TIER,
        )
