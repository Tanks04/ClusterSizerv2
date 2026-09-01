from dataclasses import dataclass
import uuid

from src.models.workload_tier import DEFAULT_WORKLOAD_TIER

# Suggested starting points for dr_category - NOT a strict enum (the
# GUI uses an editable combo) - some organizations need their own
# labels (e.g. specific regulatory/business-continuity frameworks like
# NIS/NIS2), so this is offered as a convenience default, not a limit.
DR_CATEGORIES = ["Core / Mission-Critical", "Important", "Standard", "Non-Essential"]


@dataclass
class VirtualMachine:
    """Represents one virtual machine that counts toward cluster capacity.

    Failover footprint (which sites this VM should be able to run on,
    and with what vCPU/RAM/disk on each) lives in FailoverAssignment, a
    standalone list on ClusterProject - NOT fields here - since the
    same VM can need a different footprint on different target sites
    (e.g. a smaller footprint on a budget DR site than on a full-size
    second DR), and a flat "one DR footprint" field can't represent
    that. A VM with no FailoverAssignment rows simply isn't planned to
    fail over anywhere.

    dr_category is a separate, purely informational label (e.g. "Core
    / Mission-Critical") - it does NOT gate what can be assigned in
    FailoverAssignment; that's a deliberate choice (discussed directly)
    so categorization stays a simple tag rather than a policy that
    silently blocks a valid assignment. It's useful for filtering the
    Failover Assignments table and for compliance-driven categorization
    schemes.

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
    site: str  # which site the VM currently "lives" on - one of the project's site_names

    vcpu: int
    ram_gb: float
    disk_gb: float

    powered_on: bool = True

    workload_tier: str = DEFAULT_WORKLOAD_TIER

    dr_category: str = ""  # free text, one of DR_CATEGORIES or a custom label - purely informational

    ip_address: str = ""  # guest OS IP, free text (not validated - IPv4/IPv6/hostname all fine)

    os: str = ""  # e.g. "Ubuntu Linux (64-bit)" - free text, whatever the source system reports

    vlan_uid: str = ""  # optional reference to a Vlan.uid - independent of ip_address, never required together

    # Optional reference to a Storage.uid - which specific storage pool/
    # array this VM's disk lives on, if you want to track that (some
    # VMs on one array, others on a different one, is common in
    # practice). When empty (the default, and every project before
    # this existed), disk demand only counts toward the site-wide
    # aggregate as it always has - this is purely additive, opt-in
    # per-pool tracking, same spirit as vlan_uid above.
    storage_uid: str = ""

    # Optional reference to a Cluster.uid - which specific isolated
    # cluster (a vSphere Cluster, a Nutanix cluster, a Proxmox cluster,
    # one of several independent Hyper-V Failover Clusters) this VM
    # runs in, if you want to track that. A single site commonly hosts
    # several separate clusters side by side. Same opt-in spirit as
    # storage_uid above - when empty, this VM's demand only counts
    # toward the site-wide aggregate as it always has.
    cluster_uid: str = ""

    notes: str = ""

    @staticmethod
    def create_default() -> "VirtualMachine":
        return VirtualMachine(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            vcpu=2,
            ram_gb=8.0,
            disk_gb=100.0,
            workload_tier=DEFAULT_WORKLOAD_TIER,
        )
