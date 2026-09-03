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
    and VirtualMachine.cluster_uid both optionally reference this. RVTools/
    CSV import auto-creates (or reuses) one of these from Server's
    cluster_name column via find_or_create_clusters_by_name() below,
    rather than only setting free text - see that function's docstring
    for why the two fields used to duplicate the same idea."""

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


def find_or_create_clusters_by_name(existing_clusters: list[Cluster], servers: list) -> list[Cluster]:
    """Converts each server's free-text cluster_name into a real,
    structured Cluster assignment (server.cluster_uid) - used right
    after RVTools or CSV import parses servers, before they're added to
    the project. Reported directly as confusing to have both a
    "Cluster Name" text field and a "Cluster" structured one, since
    they're really the same idea - this makes import actually populate
    the one, colored, calculation-aware Cluster system instead of a
    dead-end text field, while still starting from whatever name the
    import itself provided (which stays editable afterward, same as
    any other imported data).

    Groups servers by (site, cluster_name); reuses an existing Cluster
    if one already has that exact name at that site, otherwise creates
    one (auto-colored from the rotation). Returns only the NEWLY
    created Cluster entities - the caller adds those to the project;
    existing ones are already there and just get linked to."""
    new_clusters: list[Cluster] = []
    lookup = {(c.site, c.name): c for c in existing_clusters}

    for server in servers:
        if not server.cluster_name:
            continue
        key = (server.site, server.cluster_name)
        if key not in lookup:
            cluster = Cluster.create_default(len(existing_clusters) + len(new_clusters))
            cluster.name = server.cluster_name
            cluster.site = server.site
            lookup[key] = cluster
            new_clusters.append(cluster)
        server.cluster_uid = lookup[key].uid

    return new_clusters
