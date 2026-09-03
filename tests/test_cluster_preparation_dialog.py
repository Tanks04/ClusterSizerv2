"""Real Qt tests for ClusterPreparationWizard's GUI fixes - the
ResultPage's missing scroll area (which hid the hypervisor-CPU-
reservation warning entirely, per a real screenshot showing the text
cut off) and the "Add" confirmation (previously just appended text to
an already-overflowing label, invisible for the same reason - now a
real QMessageBox)."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea

from src.gui.dialogs.cluster_preparation_dialog import ClusterPreparationWizard
from src.models.cluster_project import ClusterProject
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _project_with_vms(count=15):
    project = ClusterProject()
    for _ in range(count):
        vm = VirtualMachine.create_default()
        vm.vcpu = 8
        vm.ram_gb = 16
        vm.disk_gb = 100
        project.vms.append(vm)
    return project


def test_result_page_content_is_scrollable():
    wizard = ClusterPreparationWizard(_project_with_vms())

    scroll_area = wizard.result_page.findChild(QScrollArea)

    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True


def test_confirm_added_shows_a_real_message_box():
    """Previously just appended text to result_label, which was already
    overflowing/clipped - invisible in practice. Now a QMessageBox that
    can't be missed."""
    wizard = ClusterPreparationWizard(_project_with_vms())

    with patch.object(QMessageBox, "information") as mock_info:
        wizard._confirm_added("Primary", 2, 1)

    assert mock_info.called
    message = mock_info.call_args[0][2]
    assert "2 Primary server(s)" in message
    assert "1 storage system(s)" in message
    assert "click Finish" in message


def test_confirm_added_message_states_nothing_saved_yet():
    """The exact confusion reported directly - users clicking Add
    repeatedly, not realizing nothing is saved until Finish."""
    wizard = ClusterPreparationWizard(_project_with_vms())

    with patch.object(QMessageBox, "information") as mock_info:
        wizard._confirm_added("DR", 1, 1)

    message = mock_info.call_args[0][2]
    assert "Nothing has been saved" in message


def test_policy_page_defaults_ht_off_and_cpu_reserve_to_two():
    wizard = ClusterPreparationWizard(_project_with_vms())

    assert wizard.policy_page.ht_check.isChecked() is False
    assert wizard.policy_page.cpu_reserve_spin.value() == 2


def test_built_policy_reflects_policy_page_choices():
    wizard = ClusterPreparationWizard(_project_with_vms())
    wizard.policy_page.ht_check.setChecked(True)
    wizard.policy_page.cpu_reserve_spin.setValue(4)

    policy = wizard.build_policy()

    assert policy.assume_hyperthreading is True
    assert policy.hypervisor_cpu_reserve_cores == 4


def test_result_page_ht_checkbox_matches_policy_choice_after_recompute():
    wizard = ClusterPreparationWizard(_project_with_vms())
    wizard.policy_page.ht_check.setChecked(True)

    wizard.recompute()

    assert wizard.result_page.ht_check.isChecked() is True


def test_manual_demand_box_visible_for_empty_project():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.show()
    wizard.workload_page.show()

    wizard.workload_page.initializePage()

    assert wizard.workload_page.manual_demand_box.isVisible() is True


def test_manual_demand_box_hidden_when_vms_exist():
    project = ClusterProject()
    vm = VirtualMachine.create_default()
    vm.site = "Primary"
    project.vms.append(vm)
    wizard = ClusterPreparationWizard(project)
    wizard.show()
    wizard.workload_page.show()

    wizard.workload_page.initializePage()

    assert wizard.workload_page.manual_demand_box.isVisible() is False


def test_manual_demand_values_flow_through_to_the_result():
    wizard = ClusterPreparationWizard(ClusterProject())
    wizard.workload_page.manual_vcpu_spin.setValue(120)
    wizard.workload_page.manual_ram_spin.setValue(240)
    wizard.workload_page.manual_disk_spin.setValue(1500)

    wizard.recompute()

    assert wizard.recommended_primary_hosts > 0
    assert "Sized from manual entry" in wizard.result_page.result_label.text()
