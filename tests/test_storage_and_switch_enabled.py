"""Tests for Storage.enabled and NetworkSwitch.enabled - lets an admin
quickly simulate "what happens if I lose/remove this array/switch"
without deleting its configuration, mirroring the existing Server.
enabled/VM.powered_on pattern exactly.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from src.calculations.networking import site_port_usage
from src.calculations.thresholds import Thresholds
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.network_switch import NetworkSwitch
from src.models.storage import Storage
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# Storage.enabled - model and calculation layer
# ----------------------------------------------------------------------

def test_storage_defaults_to_enabled():
    storage = Storage.create_default()

    assert storage.enabled is True


def test_disabled_storage_excluded_from_usable_storage_gb():
    project = ClusterProject()
    s1 = Storage.create_default()
    s1.site = PRIMARY
    s1.usable_capacity_tb = 50.0
    s2 = Storage.create_default()
    s2.site = PRIMARY
    s2.usable_capacity_tb = 30.0
    s2.enabled = False
    project.storages.extend([s1, s2])

    assert project.usable_storage_gb(PRIMARY) == 50.0 * 1024


def test_disabled_storage_affects_storage_utilization_ratio():
    project = ClusterProject()
    s1 = Storage.create_default()
    s1.site = PRIMARY
    s1.usable_capacity_tb = 0.0
    s1.enabled = False
    project.storages.append(s1)

    assert project.storage_utilization_ratio(PRIMARY) is None


def test_storage_pool_demand_gb_unaffected_by_enabled():
    """Per-storage-uid lookups (used to inspect ONE specific array's
    own utilization) should still tell the truth about VM demand
    against it, regardless of enabled status - only the aggregate
    site-wide usable_storage_gb() excludes disabled arrays."""
    from src.models.virtual_machine import VirtualMachine

    project = ClusterProject()
    storage = Storage.create_default()
    storage.enabled = False
    project.storages.append(storage)
    vm = VirtualMachine.create_default()
    vm.disk_gb = 500
    vm.storage_uid = storage.uid
    project.vms.append(vm)

    assert project.storage_pool_demand_gb(storage.uid) == 500


# ----------------------------------------------------------------------
# Storage.enabled - service layer and right-click UI
# ----------------------------------------------------------------------

def test_set_enabled_for_storages_excludes_from_capacity():
    service = ProjectService()
    storage = Storage.create_default()
    storage.site = PRIMARY
    storage.usable_capacity_tb = 50.0
    service.add_storage(storage)

    service.set_enabled_for_storages([storage], False)

    assert service.project.usable_storage_gb(PRIMARY) == 0


def test_set_enabled_for_storages_re_enable_restores():
    service = ProjectService()
    storage = Storage.create_default()
    storage.site = PRIMARY
    storage.usable_capacity_tb = 50.0
    service.add_storage(storage)
    service.set_enabled_for_storages([storage], False)

    service.set_enabled_for_storages([storage], True)

    assert service.project.usable_storage_gb(PRIMARY) == 50.0 * 1024


def test_set_enabled_for_storages_is_one_undo_step():
    service = ProjectService()
    s1 = Storage.create_default()
    s2 = Storage.create_default()
    service.add_storage(s1)
    service.add_storage(s2)

    service.set_enabled_for_storages([s1, s2], False)
    assert all(not s.enabled for s in service.project.storages)

    service.undo()

    assert all(s.enabled for s in service.project.storages)


def test_storage_page_has_disable_and_enable_actions():
    from src.gui.pages.storage_page import StoragePage

    service = ProjectService()
    page = StoragePage(service)

    labels = [l for l, _ in page.table._custom_actions]
    assert any("Disable" in l for l in labels)
    assert any("Enable" in l for l in labels)


def test_storage_page_disable_via_right_click_action():
    from src.gui.pages.storage_page import StoragePage

    service = ProjectService()
    storage = Storage.create_default()
    storage.site = PRIMARY
    storage.usable_capacity_tb = 50.0
    service.add_storage(storage)
    page = StoragePage(service)
    page.table.selectRow(0)

    page._set_enabled_for_selected(False)

    assert service.project.storages[0].enabled is False
    assert service.project.usable_storage_gb(PRIMARY) == 0


def test_storage_page_disable_with_no_selection_shows_message(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from src.gui.pages.storage_page import StoragePage

    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    service.add_storage(Storage.create_default())
    page = StoragePage(service)

    page._set_enabled_for_selected(False)

    assert informed.get("called") is True


# ----------------------------------------------------------------------
# Storage.enabled - persistence
# ----------------------------------------------------------------------

def test_storage_enabled_clsz_round_trip(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Storage enabled round trip")
    storage = Storage.create_default()
    storage.enabled = False
    project.storages.append(storage)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].enabled is False


def test_old_clsz_file_without_enabled_defaults_true(tmp_path):
    import json

    from src.persistence import project_repository

    project = ClusterProject(name="Pre-enabled")
    project.storages.append(Storage.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["storages"][0]["enabled"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].enabled is True


# ----------------------------------------------------------------------
# Storage.enabled - Word report
# ----------------------------------------------------------------------

def test_docx_report_excludes_disabled_storage_from_totals():
    from src.calculations.docx_report import build_docx_report

    project = ClusterProject()
    s1 = Storage.create_default()
    s1.site = PRIMARY
    s1.usable_capacity_tb = 50.0
    s2 = Storage.create_default()
    s2.site = PRIMARY
    s2.usable_capacity_tb = 30.0
    s2.enabled = False
    project.storages.extend([s1, s2])

    doc = build_docx_report(project, Thresholds(), app_version="test")

    summary_table = next(
        t for t in doc.tables
        if "Storage Systems (enabled)" in [c.text for c in t.rows[0].cells]
    )
    primary_row = next(r for r in summary_table.rows[1:] if r.cells[1].text == "Primary")
    assert primary_row.cells[4].text == "50.0 TB"


def test_docx_report_shows_status_column_per_storage():
    from src.calculations.docx_report import build_docx_report

    project = ClusterProject()
    storage = Storage.create_default()
    storage.enabled = False
    project.storages.append(storage)

    doc = build_docx_report(project, Thresholds(), app_version="test")

    detail_table = next(
        t for t in doc.tables
        if "Status" in [c.text for c in t.rows[0].cells]
        and "Overhead" in [c.text for c in t.rows[0].cells]
    )
    assert "Disabled" in [c.text for c in detail_table.rows[1].cells]


# ----------------------------------------------------------------------
# NetworkSwitch.enabled - model and calculation layer
# ----------------------------------------------------------------------

def test_switch_defaults_to_enabled():
    switch = NetworkSwitch.create_default()

    assert switch.enabled is True


def test_disabled_switch_excluded_from_site_port_usage():
    sw1 = NetworkSwitch.create_default()
    sw1.ports_1g = 48
    sw2 = NetworkSwitch.create_default()
    sw2.ports_1g = 24
    sw2.enabled = False

    usage = site_port_usage([sw1, sw2], [])

    total_1g = next(u.total for u in usage if u.speed == "1G")
    assert total_1g == 48


def test_per_switch_usage_still_correct_for_a_disabled_switch_directly():
    """switch_port_usage() (per-switch, used for that switch's OWN
    table row) stays unfiltered - only the site-wide aggregate
    excludes disabled switches."""
    from src.calculations.networking import switch_port_usage

    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    switch.enabled = False

    usage = switch_port_usage(switch, [])

    total_1g = next(u.total for u in usage if u.speed == "1G")
    assert total_1g == 48


# ----------------------------------------------------------------------
# NetworkSwitch.enabled - service layer and right-click UI
# ----------------------------------------------------------------------

def test_set_enabled_for_switches_excludes_from_aggregate():
    service = ProjectService()
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    service.add_switch(switch)

    service.set_enabled_for_switches([switch], False)

    usage = site_port_usage(service.project.switches, [])
    assert usage == []


def test_set_enabled_for_switches_re_enable_restores():
    service = ProjectService()
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    service.add_switch(switch)
    service.set_enabled_for_switches([switch], False)

    service.set_enabled_for_switches([switch], True)

    usage = site_port_usage(service.project.switches, [])
    total_1g = next(u.total for u in usage if u.speed == "1G")
    assert total_1g == 48


def test_set_enabled_for_switches_is_one_undo_step():
    service = ProjectService()
    sw1 = NetworkSwitch.create_default()
    sw2 = NetworkSwitch.create_default()
    service.add_switch(sw1)
    service.add_switch(sw2)

    service.set_enabled_for_switches([sw1, sw2], False)
    assert all(not s.enabled for s in service.project.switches)

    service.undo()

    assert all(s.enabled for s in service.project.switches)


def test_network_page_has_disable_and_enable_actions():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    page = NetworkPage(service)

    labels = [l for l, _ in page.switch_table._custom_actions]
    assert any("Disable" in l for l in labels)
    assert any("Enable" in l for l in labels)


def test_network_page_disable_via_right_click_action():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    switch = NetworkSwitch.create_default()
    switch.ports_1g = 48
    service.add_switch(switch)
    page = NetworkPage(service)
    page.switch_table.selectRow(0)

    page._set_enabled_for_selected_switches(False)

    assert service.project.switches[0].enabled is False


def test_network_page_disable_multi_selection():
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    for i in range(3):
        sw = NetworkSwitch.create_default()
        sw.name = f"sw{i}"
        service.add_switch(sw)
    page = NetworkPage(service)
    sel = page.switch_table.selectionModel()
    for row in (0, 1):
        sel.select(
            page.switch_table.model().index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )

    page._set_enabled_for_selected_switches(False)

    assert service.project.switches[0].enabled is False
    assert service.project.switches[1].enabled is False
    assert service.project.switches[2].enabled is True


def test_network_page_disable_with_no_selection_shows_message(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from src.gui.pages.network_page import NetworkPage

    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    service.add_switch(NetworkSwitch.create_default())
    page = NetworkPage(service)

    page._set_enabled_for_selected_switches(False)

    assert informed.get("called") is True


# ----------------------------------------------------------------------
# NetworkSwitch.enabled - persistence
# ----------------------------------------------------------------------

def test_switch_enabled_clsz_round_trip(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Switch enabled round trip")
    switch = NetworkSwitch.create_default()
    switch.enabled = False
    project.switches.append(switch)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.switches[0].enabled is False


def test_old_clsz_file_without_switch_enabled_defaults_true(tmp_path):
    import json

    from src.persistence import project_repository

    project = ClusterProject(name="Pre-enabled switch")
    project.switches.append(NetworkSwitch.create_default())
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["switches"][0]["enabled"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.switches[0].enabled is True
