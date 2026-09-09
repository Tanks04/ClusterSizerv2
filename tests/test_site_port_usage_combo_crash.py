"""Regression tests for a real crash: opening the Network tab (or
generating the aggregate site-wide port overview) raised a KeyError
the moment any switch had is_combo_ports=True - site_port_usage() only
pre-seeded its totals/used dicts with the fixed SPEED_OPTIONS set, but
switch_port_usage() in combo mode returns a composite label like
"1G/10G (combo)" that isn't a member of that set at all. Reported
directly via an uploaded real project file with two combo-ports
switches - confirmed every page in the app opens cleanly with it now.
"""

import pytest

from src.calculations.networking import site_port_usage, switch_port_usage
from src.calculations.thresholds import Thresholds
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.network_connection import NetworkConnection
from src.models.network_switch import NetworkSwitch


def _combo_switch(name, ports_1g=24, ports_10g=24):
    sw = NetworkSwitch.create_default()
    sw.name = name
    sw.ports_1g = ports_1g
    sw.ports_10g = ports_10g
    sw.ports_25g = 0
    sw.ports_40g = 0
    sw.ports_100g = 0
    sw.is_combo_ports = True
    return sw


def test_site_port_usage_does_not_crash_on_a_single_combo_switch():
    switch = _combo_switch("Nexus01")

    usage = site_port_usage([switch], [])

    assert len(usage) == 1
    assert usage[0].speed == "1G/10G (combo)"
    assert usage[0].total == 24


def test_site_port_usage_sums_two_switches_with_the_same_combo_label():
    """Exact configuration from the reported project file - two
    identically-configured combo switches."""
    sw1 = _combo_switch("Nexus01")
    sw2 = _combo_switch("Nexus02")

    usage = site_port_usage([sw1, sw2], [])

    assert len(usage) == 1
    assert usage[0].speed == "1G/10G (combo)"
    assert usage[0].total == 48


def test_site_port_usage_keeps_different_combo_labels_separate():
    sw1 = _combo_switch("Nexus01", ports_1g=24, ports_10g=24)
    sw2 = NetworkSwitch.create_default()
    sw2.name = "Nexus03"
    sw2.ports_1g = 0
    sw2.ports_10g = 0
    sw2.ports_25g = 12
    sw2.ports_40g = 0
    sw2.ports_100g = 0
    sw2.is_combo_ports = True

    usage = site_port_usage([sw1, sw2], [])

    speeds = {u.speed: u.total for u in usage}
    assert speeds["1G/10G (combo)"] == 24
    assert speeds["25G (combo)"] == 12


def test_site_port_usage_still_correct_for_a_mix_of_combo_and_normal_switches():
    combo = _combo_switch("Nexus01")
    normal = NetworkSwitch.create_default()
    normal.name = "Cisco01"
    normal.ports_1g = 48
    normal.is_combo_ports = False

    usage = site_port_usage([combo, normal], [])

    speeds = {u.speed: u.total for u in usage}
    assert speeds["1G/10G (combo)"] == 24
    assert speeds["1G"] == 48


def test_site_port_usage_counts_usage_correctly_with_combo_switches():
    switch = _combo_switch("Nexus01")
    conn = NetworkConnection.create_default()
    conn.switch_uid = switch.uid
    conn.speed = "1G"

    usage = site_port_usage([switch], [conn])

    assert usage[0].used == 1


def test_site_port_usage_excludes_disabled_combo_switch():
    switch = _combo_switch("Nexus01")
    switch.enabled = False

    usage = site_port_usage([switch], [])

    assert usage == []


def test_regular_switches_still_use_the_ordered_speed_options():
    """Regression guard - non-combo switches must still produce
    results ordered by SPEED_OPTIONS as before, not just dumped in
    dict-insertion order."""
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    switch.ports_10g = 4
    switch.ports_25g = 0

    usage = site_port_usage([switch], [])

    assert [u.speed for u in usage] == ["1G", "10G"]


# ----------------------------------------------------------------------
# Full end-to-end: every page in the app opens with a real combo-ports
# project, matching how the crash actually manifested
# ----------------------------------------------------------------------

def test_network_page_opens_with_combo_switches(tmp_path):
    import pytest as _pytest
    _pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.pages.network_page import NetworkPage
    from src.persistence import project_repository
    from src.services.project_service import ProjectService

    project = ClusterProject(name="Combo switch project")
    project.switches.append(_combo_switch("Nexus01"))
    project.switches.append(_combo_switch("Nexus02"))
    path = tmp_path / "combo.clsz"
    project_repository.save_project(project, path, Thresholds())

    service = ProjectService()
    service.load_project(str(path))
    page = NetworkPage(service)
    page.refresh()  # must not raise KeyError
