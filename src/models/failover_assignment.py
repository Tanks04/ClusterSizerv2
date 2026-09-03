import uuid
from dataclasses import dataclass


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

    # Set via right-click "Acknowledge" on the Failover Assignments table
    # when a footprint exceeding the VM's current size is INTENTIONAL
    # (e.g. a deliberately over-provisioned warm standby) rather than
    # stale/forgotten - silences the Attention Needed warning and the
    # table's orange marker for this specific assignment. Does NOT
    # reset automatically if the numbers change again later - toggle it
    # off manually via the same action if you want the warning back.
    footprint_confirmed: bool = False

    @staticmethod
    def create_default() -> "FailoverAssignment":
        return FailoverAssignment(
            uid=str(uuid.uuid4()),
            vm_uid="",
            target_site="",
        )
