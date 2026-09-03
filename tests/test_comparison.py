from src.calculations.comparison import projects_are_identical
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.server import Server


def test_identical_ignores_uid():
    a = ClusterProject(name="A")
    s1 = Server.create_default()
    s1.name = "esxi01"
    s1.site = PRIMARY
    s1.ram_gb = 256
    a.servers.append(s1)

    b = ClusterProject(name="B (different name, on purpose)")
    s2 = Server.create_default()
    s2.name = "esxi01"
    s2.site = PRIMARY
    s2.ram_gb = 256
    b.servers.append(s2)

    assert s1.uid != s2.uid
    assert projects_are_identical(a, b) is True


def test_identical_detects_value_change():
    a = ClusterProject(name="A")
    s1 = Server.create_default()
    s1.site = PRIMARY
    s1.ram_gb = 256
    a.servers.append(s1)

    b = ClusterProject(name="A")
    s2 = Server.create_default()
    s2.site = PRIMARY
    s2.ram_gb = 512
    b.servers.append(s2)

    assert projects_are_identical(a, b) is False
