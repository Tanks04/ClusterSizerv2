"""Tests for switch redundancy modeling - a colored border for paired
devices (HSRP/VRRP switch pairs, Active/Passive firewall HA pairs,
MLAG/VPC stacks - "Firewall" and "Load Balancer" are just switch_type
values on the same NetworkSwitch, so this works for those too),
Switch<->Switch connections, and dedicated/proprietary links that
don't consume a declared port."""

from src.models.network_switch import NetworkSwitch, REDUNDANCY_ROLES, redundancy_group_color
from src.models.network_connection import NetworkConnection, KIND_SWITCH_SWITCH, KIND_SERVER_SWITCH
from src.calculations.networking import switch_port_usage
from src.persistence import csv_io, project_repository
from src.models.cluster_project import ClusterProject
from src.calculations.thresholds import Thresholds


# ----------------------------------------------------------------------
# redundancy_group_color - deterministic, stable across process restarts
# ----------------------------------------------------------------------

def test_same_group_name_always_gets_the_same_color():
    assert redundancy_group_color("core-pair-01") == redundancy_group_color("core-pair-01")


def test_different_group_names_get_different_colors():
    assert redundancy_group_color("core-pair-01") != redundancy_group_color("core-pair-02")


def test_blank_group_has_no_color():
    assert redundancy_group_color("") is None


def test_color_is_stable_across_hash_seeds():
    """Python's built-in hash() is salted per-process (PYTHONHASHSEED) -
    this must NOT be used, or the same group would get a different
    color every time the app restarts."""
    import subprocess
    import sys

    results = set()
    for seed in ("0", "1", "42"):
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from src.models.network_switch import redundancy_group_color; "
             "print(redundancy_group_color('core-pair-01'))"],
            capture_output=True, text=True, env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        results.add(out.stdout.strip())

    assert len(results) == 1


# ----------------------------------------------------------------------
# NetworkSwitch fields
# ----------------------------------------------------------------------

def test_switch_redundancy_fields_default_empty():
    s = NetworkSwitch.create_default()
    assert s.redundancy_group == ""
    assert s.redundancy_role == ""


def test_redundancy_roles_cover_common_vendor_terminology():
    assert "Active" in REDUNDANCY_ROLES
    assert "Standby" in REDUNDANCY_ROLES  # Cisco HSRP/VRRP/GLBP
    assert "Passive" in REDUNDANCY_ROLES  # Palo Alto/Fortinet HA pairs
    assert "Member" in REDUNDANCY_ROLES   # MLAG/VPC/stacking


# ----------------------------------------------------------------------
# NetworkConnection - Switch<->Switch and dedicated_link
# ----------------------------------------------------------------------

def test_switch_to_switch_connection_kind():
    conn = NetworkConnection.create_default()
    conn.switch_uid = "sw1"
    conn.switch_b_uid = "sw2"

    assert conn.connection_kind == KIND_SWITCH_SWITCH


def test_server_switch_connection_kind_unaffected():
    conn = NetworkConnection.create_default()
    conn.server_uid = "srv1"
    conn.switch_uid = "sw1"

    assert conn.connection_kind == KIND_SERVER_SWITCH


def test_dedicated_link_defaults_false():
    conn = NetworkConnection.create_default()
    assert conn.dedicated_link is False


def test_dedicated_link_excluded_from_port_usage():
    """The exact scenario reported: a proprietary stacking/HA-sync
    cable (e.g. Cisco StackWise) that doesn't consume one of the
    device's declared ports."""
    sw = NetworkSwitch.create_default()
    sw.ports_10g = 4

    normal = NetworkConnection.create_default()
    normal.switch_uid = sw.uid
    normal.server_uid = "srv1"
    normal.speed = "10G"

    dedicated = NetworkConnection.create_default()
    dedicated.switch_uid = sw.uid
    dedicated.switch_b_uid = "sw2"
    dedicated.speed = "10G"
    dedicated.dedicated_link = True

    usage = switch_port_usage(sw, [normal, dedicated])
    ten_g = next(u for u in usage if u.speed == "10G")

    assert ten_g.used == 1  # only the normal connection counts


# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------

def test_clsz_round_trip(tmp_path):
    project = ClusterProject(name="Redundancy round trip")
    sw1 = NetworkSwitch.create_default()
    sw1.name = "fw-01"
    sw1.redundancy_group = "fw-pair-01"
    sw1.redundancy_role = "Active"
    sw2 = NetworkSwitch.create_default()
    sw2.name = "fw-02"
    sw2.redundancy_group = "fw-pair-01"
    sw2.redundancy_role = "Passive"
    project.switches.extend([sw1, sw2])
    conn = NetworkConnection.create_default()
    conn.switch_uid = sw1.uid
    conn.switch_b_uid = sw2.uid
    conn.dedicated_link = True
    project.connections.append(conn)

    path = tmp_path / "r.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.switches[0].redundancy_group == "fw-pair-01"
    assert loaded.project.switches[0].redundancy_role == "Active"
    assert loaded.project.connections[0].switch_b_uid == sw2.uid
    assert loaded.project.connections[0].dedicated_link is True


def test_old_clsz_file_without_new_fields_defaults_gracefully(tmp_path):
    import json
    project = ClusterProject(name="Pre-redundancy")
    project.switches.append(NetworkSwitch.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["switches"][0]["redundancy_group"]
    del raw["switches"][0]["redundancy_role"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.switches[0].redundancy_group == ""


def test_switch_csv_round_trip(tmp_path):
    sw = NetworkSwitch.create_default()
    sw.redundancy_group = "core-pair-01"
    sw.redundancy_role = "Active"
    path = tmp_path / "sw.csv"
    csv_io.export_switches(path, [sw])

    loaded = csv_io.import_switches(path)

    assert loaded[0].redundancy_group == "core-pair-01"
    assert loaded[0].redundancy_role == "Active"


def test_connection_csv_round_trip_with_switch_b_and_dedicated(tmp_path):
    sw1 = NetworkSwitch.create_default()
    sw1.name = "sw-01"
    sw2 = NetworkSwitch.create_default()
    sw2.name = "sw-02"
    conn = NetworkConnection.create_default()
    conn.switch_uid = sw1.uid
    conn.switch_b_uid = sw2.uid
    conn.dedicated_link = True
    path = tmp_path / "conn.csv"
    csv_io.export_connections(path, [conn], [], [sw1, sw2], [])

    loaded, skipped = csv_io.import_connections(path, [], [sw1, sw2], [])

    assert skipped == 0
    assert loaded[0].switch_b_uid == sw2.uid
    assert loaded[0].dedicated_link is True


def test_old_switch_csv_without_redundancy_columns_still_imports(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("name,site,switch_type\nold-sw,Primary,LAN\n", encoding="utf-8")

    loaded = csv_io.import_switches(path)

    assert loaded[0].redundancy_group == ""
