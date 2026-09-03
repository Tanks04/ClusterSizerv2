"""Tests for the Cluster entity - an isolated compute failure domain
(a vSphere Cluster, a Nutanix cluster, a Proxmox cluster, one of
several independent Hyper-V Failover Clusters) that a single site can
host several of side by side. Mirrors the Storage Pool pattern
exactly: per-cluster CPU/RAM tracking reveals problems the site-wide
aggregate can hide."""

from src.calculations.thresholds import Thresholds
from src.models.cluster import DEFAULT_CLUSTER_COLORS, Cluster
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.persistence import csv_io, project_repository
from src.services.project_service import ProjectService


def test_cluster_create_default_rotates_colors():
    c1 = Cluster.create_default(0)
    c2 = Cluster.create_default(1)
    assert c1.color != c2.color
    assert c1.color == DEFAULT_CLUSTER_COLORS[0]
    assert c2.color == DEFAULT_CLUSTER_COLORS[1]


def test_server_cluster_uid_defaults_empty_and_cluster_name_unaffected():
    s = Server.create_default()
    assert s.cluster_uid == ""
    s.cluster_name = "vSAN_HPM"  # existing free-text field still works independently
    assert s.cluster_name == "vSAN_HPM"
    assert s.cluster_uid == ""


def test_vm_cluster_uid_defaults_empty():
    vm = VirtualMachine.create_default()
    assert vm.cluster_uid == ""


def test_clsz_round_trip(tmp_path):
    project = ClusterProject(name="Cluster round trip")
    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-A"
    cluster.site = PRIMARY
    project.clusters.append(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    project.servers.append(server)
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid
    project.vms.append(vm)

    path = tmp_path / "c.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert len(loaded.project.clusters) == 1
    assert loaded.project.clusters[0].name == "Cluster-A"
    assert loaded.project.clusters[0].color == cluster.color
    assert loaded.project.servers[0].cluster_uid == cluster.uid
    assert loaded.project.vms[0].cluster_uid == cluster.uid


def test_old_clsz_file_without_clusters_defaults_gracefully(tmp_path):
    import json
    project = ClusterProject(name="Pre-cluster-feature")
    project.servers.append(Server.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["clusters"]
    del raw["servers"][0]["cluster_uid"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.clusters == []
    assert loaded.project.servers[0].cluster_uid == ""


# ----------------------------------------------------------------------
# Per-cluster CPU/RAM tracking
# ----------------------------------------------------------------------

def _server_with_cluster(cluster_uid, sockets, cores_per_socket, ram_gb=256.0):
    s = Server.create_default()
    s.site = PRIMARY
    s.cluster_uid = cluster_uid
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.hyperthreading_enabled = False
    s.ram_gb = ram_gb
    return s


def _vm_with_cluster(cluster_uid, vcpu, ram_gb=8.0):
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster_uid
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    vm.powered_on = True
    return vm


def test_cluster_physical_cores_only_counts_assigned_servers():
    project = ClusterProject()
    cluster_a = Cluster.create_default(0)
    cluster_b = Cluster.create_default(1)
    project.servers.append(_server_with_cluster(cluster_a.uid, 1, 8))
    project.servers.append(_server_with_cluster(cluster_b.uid, 2, 32))

    assert project.cluster_physical_cores(cluster_a.uid) == 8
    assert project.cluster_physical_cores(cluster_b.uid) == 64


def test_unassigned_servers_never_count_toward_any_cluster():
    project = ClusterProject()
    cluster = Cluster.create_default(0)
    project.servers.append(Server.create_default())  # cluster_uid left empty

    assert project.cluster_physical_cores(cluster.uid) == 0


def test_cluster_reveals_oversubscription_the_site_aggregate_hides():
    """The exact scenario this feature exists for: two isolated
    clusters at one site, one badly oversubscribed, one nearly idle -
    the site-wide aggregate looks perfectly healthy (1:1) while
    Cluster A specifically is critically oversubscribed (8:1)."""
    project = ClusterProject()
    cluster_a = Cluster.create_default(0)
    cluster_a.site = PRIMARY
    cluster_b = Cluster.create_default(1)
    cluster_b.site = PRIMARY
    project.clusters.extend([cluster_a, cluster_b])

    project.servers.append(_server_with_cluster(cluster_a.uid, 1, 8))
    project.vms.append(_vm_with_cluster(cluster_a.uid, 64))
    project.servers.append(_server_with_cluster(cluster_b.uid, 2, 32))
    project.vms.append(_vm_with_cluster(cluster_b.uid, 8))

    assert project.cluster_cpu_ratio(cluster_a.uid) == 8.0
    assert project.cluster_cpu_ratio(cluster_b.uid) == 0.125
    assert project.cpu_oversubscription_ratio(PRIMARY) == 1.0


def test_cluster_ram_ratio_none_when_no_servers_assigned():
    project = ClusterProject()
    cluster = Cluster.create_default(0)

    assert project.cluster_ram_ratio(cluster.uid) is None
    assert project.cluster_cpu_ratio(cluster.uid) is None


def test_powered_off_vms_excluded_from_cluster_demand():
    project = ClusterProject()
    cluster = Cluster.create_default(0)
    project.servers.append(_server_with_cluster(cluster.uid, 2, 16))
    vm = _vm_with_cluster(cluster.uid, 32)
    vm.powered_on = False
    project.vms.append(vm)

    assert project.cluster_vcpu_demand(cluster.uid) == 0


# ----------------------------------------------------------------------
# ProjectService CRUD - cascade clear on BOTH Server and VM (unlike
# VLAN, which only VMs reference)
# ----------------------------------------------------------------------

def test_add_cluster():
    service = ProjectService()
    cluster = Cluster.create_default(0)

    service.add_cluster(cluster)

    assert len(service.project.clusters) == 1


def test_remove_clusters_cascades_to_both_server_and_vm():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid
    service.add_vm(vm)

    service.remove_clusters([cluster])

    assert service.project.clusters == []
    assert service.project.servers[0].cluster_uid == ""
    assert service.project.vms[0].cluster_uid == ""


def test_remove_clusters_is_undoable():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)

    service.remove_clusters([cluster])
    service.undo()

    assert len(service.project.clusters) == 1
    assert service.project.servers[0].cluster_uid == cluster.uid


def test_clear_clusters_cascades_to_both():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    server = Server.create_default()
    server.cluster_uid = cluster.uid
    service.add_server(server)
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid
    service.add_vm(vm)

    service.clear_clusters()

    assert service.project.clusters == []
    assert service.project.servers[0].cluster_uid == ""
    assert service.project.vms[0].cluster_uid == ""


def test_update_cluster():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)

    updated = Cluster(uid=cluster.uid, name="Renamed", site=PRIMARY, color="#000000")
    service.update_cluster(0, updated)

    assert service.project.clusters[0].name == "Renamed"
