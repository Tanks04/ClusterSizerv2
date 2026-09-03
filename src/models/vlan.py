import uuid
from dataclasses import dataclass


@dataclass
class Vlan:
    """A network segment (VLAN) that VMs can be assigned to - independent
    of any specific Switch, since a real VLAN is a logical construct
    that commonly trunks across several physical switches rather than
    belonging to just one. Site-scoped like everything else. IP
    addressing on a VM is a completely separate, optional field -
    assigning a VM to a VLAN never requires also giving it an IP."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    network: str = ""    # free text, e.g. "192.168.10.0/24"
    gateway: str = ""    # free text, e.g. "192.168.10.1"
    notes: str = ""

    @staticmethod
    def create_default() -> "Vlan":
        return Vlan(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
        )
