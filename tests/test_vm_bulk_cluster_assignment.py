"""Real Qt tests for bulk-assigning VMs to a Cluster - both the right-
click "Add to Cluster (name)" per-cluster action and the "Bulk move
(Cluster)" toolbar row (Move Selected/Move All), matching the exact
patterns already established for Site and Failover assignment. The
scenario this exists for: assigning 70 VMs to a cluster one dialog at
a time was reported directly as far too slow."""

import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.services.project_service import ProjectService
from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.models.cluster import Cluster
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _vms(service, count=5):
    vms = []
    for i in range(count):
        vm = VirtualMachine.create_default()
        vm.name = f"vm-{i}"
        service.add_vm(vm)
        vms.append(vm)
    return vms


# ----------------------------------------------------------------------
# Right-click "Add to Cluster"
# ----------------------------------------------------------------------

def test_custom_actions_list_one_entry_per_cluster():
    service = ProjectService()
    cluster_a = Cluster.create_default(0)
    cluster_a.name = "HV-Cluster-A"
    cluster_b = Cluster.create_default(1)
    cluster_b.name = "HV-Cluster-B"
    service.add_cluster(cluster_a)
    service.add_cluster(cluster_b)
    page = VirtualMachinesPage(service)

    labels = [label for label, _ in page.table._custom_actions]

    assert any("Add to Cluster (HV-Cluster-A)" in l for l in labels)
    assert any("Add to Cluster (HV-Cluster-B)" in l for l in labels)


def test_add_selected_to_cluster_assigns_all_selected_at_once():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 70)  # the exact scale reported directly
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._add_selected_to_cluster(cluster.uid)

    assert all(vm.cluster_uid == cluster.uid for vm in service.project.vms)


def test_add_selected_to_cluster_is_one_undo_step():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 5)
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._add_selected_to_cluster(cluster.uid)
    service.undo()

    assert all(vm.cluster_uid == "" for vm in service.project.vms)


def test_add_selected_to_cluster_with_no_selection_does_nothing():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    page._add_selected_to_cluster(cluster.uid)

    assert all(vm.cluster_uid == "" for vm in service.project.vms)


# ----------------------------------------------------------------------
# Bulk move (Cluster) toolbar row
# ----------------------------------------------------------------------

def test_bulk_cluster_combo_populated_from_project_clusters():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    cluster.name = "HV-Cluster-A"
    service.add_cluster(cluster)
    page = VirtualMachinesPage(service)

    assert page.bulk_cluster_combo.count() == 1
    assert page.bulk_cluster_combo.currentText() == "HV-Cluster-A"
    assert page.bulk_cluster_combo.currentData() == cluster.uid


def test_move_selected_to_cluster_only_affects_selected_vms():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    vms = _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectRow(0)

    page._set_cluster_for_selected_from_combo()

    assert vms[0].cluster_uid == cluster.uid
    assert vms[1].cluster_uid == ""
    assert vms[2].cluster_uid == ""


def test_move_selected_to_cluster_with_no_selection_shows_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 3)
    page = VirtualMachinesPage(service)

    page._set_cluster_for_selected_from_combo()

    assert informed.get("called") is True


def test_move_all_to_cluster_assigns_every_vm():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 70)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        page._set_all_vms_cluster()

    assert all(vm.cluster_uid == cluster.uid for vm in service.project.vms)


def test_move_all_to_cluster_cancelled_changes_nothing():
    service = ProjectService()
    cluster = Cluster.create_default(0)
    service.add_cluster(cluster)
    _vms(service, 5)
    page = VirtualMachinesPage(service)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        page._set_all_vms_cluster()

    assert all(vm.cluster_uid == "" for vm in service.project.vms)


def test_no_clusters_yet_shows_a_helpful_message(monkeypatch):
    informed = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.setdefault("called", True))
    service = ProjectService()
    _vms(service, 3)
    page = VirtualMachinesPage(service)
    page.table.selectAll()

    page._set_cluster_for_selected_from_combo()

    assert informed.get("called") is True


def test_cluster_combo_preserves_selection_across_refresh():
    service = ProjectService()
    cluster_a = Cluster.create_default(0)
    cluster_a.name = "HV-Cluster-A"
    cluster_b = Cluster.create_default(1)
    cluster_b.name = "HV-Cluster-B"
    service.add_cluster(cluster_a)
    service.add_cluster(cluster_b)
    page = VirtualMachinesPage(service)
    page.bulk_cluster_combo.setCurrentIndex(1)

    _vms(service, 1)  # triggers a refresh via vms_changed

    assert page.bulk_cluster_combo.currentData() == cluster_b.uid
