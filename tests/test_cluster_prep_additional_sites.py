"""Real Qt tests for the Cluster Preparation wizard's Additional Sites
page - the N-site recommendation path driven by DR Category selection,
plus the auto-created Failover Assignments when adding a site cluster."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _bank_project():
    project = ClusterProject()
    project.add_site("DR2")
    vm_plan = [
        ("core-banking-01", 8, 32, 500, "Core / Mission-Critical"),
        ("payments-01", 8, 32, 500, "Core / Mission-Critical"),
        ("crm-01", 6, 24, 300, "Important"),
        ("reporting-01", 6, 32, 500, "Standard"),
        ("dwh-01", 8, 32, 500, "Non-Essential"),
        ("test-env-01", 4, 16, 200, "Non-Essential"),
    ]
    for name, vcpu, ram, disk, category in vm_plan:
        vm = VirtualMachine.create_default()
        vm.name = name
        vm.site = PRIMARY
        vm.vcpu = vcpu
        vm.ram_gb = ram
        vm.disk_gb = disk
        vm.dr_category = category
        project.vms.append(vm)
    return project


def test_one_widget_block_per_non_primary_site():
    project = ClusterProject()  # default Primary + DR
    project.add_site("DR2")
    wizard = ClusterPreparationWizard(project)

    wizard.additional_sites_page.initializePage()

    assert set(wizard.additional_sites_page._site_widgets.keys()) == {"DR", "DR2"}


def test_default_category_selection_is_core_and_important_only():
    project = ClusterProject()
    wizard = ClusterPreparationWizard(project)
    wizard.additional_sites_page.initializePage()

    widgets = wizard.additional_sites_page._site_widgets["DR"]
    widgets["box"].setChecked(True)

    selected = wizard.additional_sites_page.selected_categories("DR")
    assert selected == {"Core / Mission-Critical", "Important"}


def test_unchecked_site_box_returns_no_selected_categories():
    project = ClusterProject()
    wizard = ClusterPreparationWizard(project)
    wizard.additional_sites_page.initializePage()

    selected = wizard.additional_sites_page.selected_categories("DR")

    assert selected == set()


def test_add_site_cluster_creates_matching_failover_assignments():
    """The exact bank scenario - Core/Important/Standard included for
    DR2, Non-Essential excluded, matching the discussed 'everything
    except DWH and test/dev' policy."""
    project = _bank_project()
    wizard = ClusterPreparationWizard(project)
    wizard.recompute()
    wizard.additional_sites_page.initializePage()

    dr2 = wizard.additional_sites_page._site_widgets["DR2"]
    dr2["box"].setChecked(True)
    dr2["category_checks"]["Standard"].setChecked(True)

    with patch.object(QMessageBox, "information"):
        wizard.add_site_cluster("DR2")

    assert len(wizard.new_failover_assignments) == 4
    assert all(a.target_site == "DR2" for a in wizard.new_failover_assignments)
    assigned_names = {
        next(v.name for v in project.vms if v.uid == a.vm_uid)
        for a in wizard.new_failover_assignments
    }
    assert assigned_names == {"core-banking-01", "payments-01", "crm-01", "reporting-01"}


def test_add_site_cluster_queues_servers_and_storage():
    project = _bank_project()
    wizard = ClusterPreparationWizard(project)
    wizard.recompute()
    wizard.additional_sites_page.initializePage()
    dr2 = wizard.additional_sites_page._site_widgets["DR2"]
    dr2["box"].setChecked(True)

    with patch.object(QMessageBox, "information"):
        wizard.add_site_cluster("DR2")

    assert "DR2" in wizard.new_site_clusters
    servers, storages = wizard.new_site_clusters["DR2"]
    assert len(servers) > 0
    assert all(s.site == "DR2" for s in servers)


def test_re_adding_a_site_replaces_its_queued_assignments_not_duplicates():
    project = _bank_project()
    wizard = ClusterPreparationWizard(project)
    wizard.recompute()
    wizard.additional_sites_page.initializePage()
    dr2 = wizard.additional_sites_page._site_widgets["DR2"]
    dr2["box"].setChecked(True)

    with patch.object(QMessageBox, "information"):
        wizard.add_site_cluster("DR2")
        first_count = len(wizard.new_failover_assignments)
        wizard.add_site_cluster("DR2")  # click Add again without changing selection
        second_count = len(wizard.new_failover_assignments)

    assert first_count == second_count == 3


def test_failover_assignment_footprint_defaults_to_vm_own_size():
    project = _bank_project()
    wizard = ClusterPreparationWizard(project)
    wizard.recompute()
    wizard.additional_sites_page.initializePage()
    dr2 = wizard.additional_sites_page._site_widgets["DR2"]
    dr2["box"].setChecked(True)

    with patch.object(QMessageBox, "information"):
        wizard.add_site_cluster("DR2")

    core_vm = next(v for v in project.vms if v.name == "core-banking-01")
    assignment = next(a for a in wizard.new_failover_assignments if a.vm_uid == core_vm.uid)
    assert assignment.vcpu == core_vm.vcpu
    assert assignment.ram_gb == core_vm.ram_gb
    assert assignment.disk_gb == core_vm.disk_gb


def test_no_categories_selected_produces_no_assignments():
    project = _bank_project()
    wizard = ClusterPreparationWizard(project)
    wizard.recompute()
    wizard.additional_sites_page.initializePage()
    dr2 = wizard.additional_sites_page._site_widgets["DR2"]
    dr2["box"].setChecked(True)
    for check in dr2["category_checks"].values():
        check.setChecked(False)

    with patch.object(QMessageBox, "information"):
        wizard.add_site_cluster("DR2")

    assert wizard.new_failover_assignments == []
