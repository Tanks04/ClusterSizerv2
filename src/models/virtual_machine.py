from dataclasses import dataclass
import uuid


@dataclass
class VirtualMachine:
    """Predstavlja jednu virtualnu mašinu koja se računa u kapacitet klastera.

    dr_protected + dr_* polja postoje jer VM-ovi često NISU 1:1 replicirani
    na DR (npr. replicira se s manje resursa, ili se uopće ne replicira).
    Kad dr_protected=False, VM se ne računa u DR failover potražnju - samo
    troši resurse na svojoj matičnoj (site) lokaciji.
    """

    uid: str
    name: str
    site: str  # "Primary" | "DR" - na kojem clusteru VM trenutno "živi"

    vcpu: int
    ram_gb: float
    disk_gb: float

    powered_on: bool = True

    dr_protected: bool = False  # replicira li se ovaj VM na DR (failover)?
    dr_vcpu: int = 0            # footprint na DR - može biti manji od vcpu
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
