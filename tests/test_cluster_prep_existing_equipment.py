"""Real Qt tests for VirtualMachinesPage._apply_cluster_prep_site - the
Add/Replace/Cancel prompt shown when Cluster Preparation's recommended
servers/storage would land on a site that already has some, confirming
the exact reported request ("should ask whether to clear existing or
add these")."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.pages.virtual_machines_page import VirtualMachinesPage
from src.models.cluster_project import PRIMARY
from src.models.server import Server
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_no_prompt_when_site_is_empty():
    """No existing equipment - just adds, no question asked."""
    service = ProjectService()
    page = VirtualMachinesPage(service)
    new_server = Server.create_default()
    new_server.site = PRIMARY

    with patch.object(QMessageBox, "question") as mock_question, \
         patch.object(QMessageBox, "information"):
        page._apply_cluster_prep_site(PRIMARY, [new_server], [])

    assert not mock_question.called
    assert len(service.project.servers) == 1


def test_add_choice_keeps_existing_and_adds_new():
    service = ProjectService()
    existing = Server.create_default()
    existing.site = PRIMARY
    service.add_server(existing)
    page = VirtualMachinesPage(service)
    new_server = Server.create_default()
    new_server.site = PRIMARY

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"):
        page._apply_cluster_prep_site(PRIMARY, [new_server], [])

    assert len(service.project.servers) == 2


def test_replace_choice_removes_existing_and_adds_new():
    service = ProjectService()
    existing = Server.create_default()
    existing.site = PRIMARY
    service.add_server(existing)
    page = VirtualMachinesPage(service)
    new_server = Server.create_default()
    new_server.site = PRIMARY

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._apply_cluster_prep_site(PRIMARY, [new_server], [])

    assert len(service.project.servers) == 1
    assert service.project.servers[0].uid == new_server.uid


def test_cancel_choice_leaves_the_project_untouched():
    service = ProjectService()
    existing = Server.create_default()
    existing.site = PRIMARY
    service.add_server(existing)
    page = VirtualMachinesPage(service)
    new_server = Server.create_default()
    new_server.site = PRIMARY

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
        page._apply_cluster_prep_site(PRIMARY, [new_server], [])

    assert len(service.project.servers) == 1
    assert service.project.servers[0].uid == existing.uid


def test_replace_only_affects_the_target_site_not_others():
    from src.models.cluster_project import DR

    service = ProjectService()
    primary_existing = Server.create_default()
    primary_existing.site = PRIMARY
    dr_existing = Server.create_default()
    dr_existing.site = DR
    service.add_server(primary_existing)
    service.add_server(dr_existing)
    page = VirtualMachinesPage(service)
    new_server = Server.create_default()
    new_server.site = PRIMARY

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._apply_cluster_prep_site(PRIMARY, [new_server], [])

    sites = {s.site for s in service.project.servers}
    assert DR in sites
    assert len([s for s in service.project.servers if s.site == DR]) == 1


def test_open_cluster_preparation_applies_generic_n_site_clusters_and_assignments(monkeypatch):
    """Confirms VirtualMachinesPage._open_cluster_preparation() actually
    reads back and commits dialog.new_site_clusters / new_failover_
    assignments after the wizard closes - not just the fixed Primary/DR
    queues that existed before N-site support."""
    from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
    from src.models.failover_assignment import FailoverAssignment
    from src.models.server import Server
    from src.models.virtual_machine import VirtualMachine

    service = ProjectService()
    vm = VirtualMachine.create_default()
    service.add_vm(vm)
    page = VirtualMachinesPage(service)

    fake_server = Server.create_default()
    fake_server.site = "DR2"
    fake_assignment = FailoverAssignment.create_default()
    fake_assignment.vm_uid = vm.uid
    fake_assignment.target_site = "DR2"

    def fake_exec(self):
        self.new_site_clusters["DR2"] = ([fake_server], [])
        self.new_failover_assignments = [fake_assignment]
        return 1

    monkeypatch.setattr(ClusterPreparationWizard, "exec", fake_exec)

    with patch.object(QMessageBox, "information"):
        page._open_cluster_preparation()

    assert any(s.site == "DR2" for s in service.project.servers)
    assert len(service.project.failover_assignments) == 1
    assert service.project.failover_assignments[0].target_site == "DR2"


def test_open_cluster_preparation_commits_queued_backup_destinations(monkeypatch):
    from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
    from src.models.backup_destination import BackupDestination

    service = ProjectService()
    page = VirtualMachinesPage(service)

    fake_destination = BackupDestination.create_default()
    fake_destination.name = "wizard-backup"

    def fake_exec(self):
        self.new_backup_destinations = [fake_destination]
        return 1

    monkeypatch.setattr(ClusterPreparationWizard, "exec", fake_exec)

    page._open_cluster_preparation()

    assert len(service.project.backup_destinations) == 1
    assert service.project.backup_destinations[0].name == "wizard-backup"
