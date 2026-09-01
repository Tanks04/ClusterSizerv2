from dataclasses import dataclass
import uuid

# A reasonable, distinguishable default palette - the person can pick
# any color regardless, this just gives the first Cluster created a
# sensible starting color rather than "no color".
DEFAULT_CLUSTER_COLORS = [
    "#e57373",  # red
    "#64b5f6",  # blue
    "#81c784",  # green
    "#ffb74d",  # orange
    "#ba68c8",  # purple
    "#4db6ac",  # teal
    "#f06292",  # pink
    "#a1887f",  # brown
]


@dataclass
class Cluster:
    """An isolated compute failure domain (a vSphere Cluster, a Nutanix
    cluster, a Proxmox cluster, a Hyper-V Failover Cluster instance) -
    ClusterSizer's own "site" concept is about physical location
    (Primary/DR/...), but a single site commonly hosts SEVERAL separate,
    independent clusters side by side (e.g. 6 hosts at Primary split
    into two 3-node Hyper-V clusters, or a VMware environment with
    Cluster-A and Cluster-B in the same datacenter). Server.cluster_uid
    and VirtualMachine.cluster_uid both optionally reference this -
    separate from Server's existing free-text cluster_name field
    (which stays exactly as-is, since RVTools/other imports already
    populate it as plain informational text). Purely additive and
    opt-in: nothing changes for a project that never creates one."""

    uid: str
    name: str
    site: str  # "Primary" | "DR" | ...
    color: str = "#64b5f6"  # hex color, shown as a badge in tables/dropdowns
    notes: str = ""

    @staticmethod
    def create_default(existing_count: int = 0) -> "Cluster":
        color = DEFAULT_CLUSTER_COLORS[existing_count % len(DEFAULT_CLUSTER_COLORS)]
        return Cluster(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            color=color,
        )
