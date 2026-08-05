from dataclasses import dataclass
import uuid


@dataclass
class VirtualMachine:
    """Represents one virtual machine that counts toward cluster capacity.

    dr_protected + dr_* fields exist because VMs are often NOT replicated
    1:1 to DR (e.g. replicated with fewer resources, or not replicated at
    all). When dr_protected=False, the VM is not counted in DR failover
    demand - it only consumes resources at its home (site) location.
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
        )
