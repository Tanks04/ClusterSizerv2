from dataclasses import dataclass
import uuid


@dataclass
class FailoverAssignment:
    """One VM's failover footprint on ONE target site. A standalone list
    on ClusterProject, not nested inside VirtualMachine - the same VM
    can appear in several rows (one per target site) with a DIFFERENT
    footprint on each, since what a VM needs to run acceptably on site
    B isn't necessarily what it needs on site C (different available
    hardware, different acceptable degraded-mode sizing). References
    the VM by uid - if the VM is later deleted, ProjectService removes
    its assignments too (no orphaned rows pointing at nothing)."""

    uid: str
    vm_uid: str
    target_site: str

    vcpu: int = 0
    ram_gb: float = 0.0
    disk_gb: float = 0.0

    @staticmethod
    def create_default() -> "FailoverAssignment":
        return FailoverAssignment(
            uid=str(uuid.uuid4()),
            vm_uid="",
            target_site="",
        )
