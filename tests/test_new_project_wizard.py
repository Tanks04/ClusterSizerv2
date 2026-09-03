"""Tests for the New Project Wizard (File > New with Wizard) - a few
quick questions (sites, hypervisor, a rough VM count) that set up
sensible starting defaults instead of an empty project."""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.calculations.vm_generation import generate_vms
from src.gui.dialogs.new_project_wizard_dialog import NewProjectWizardDialog
from src.gui.main_window import MainWindow
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# generate_vms - pure calculation
# ----------------------------------------------------------------------

def test_generate_vms_splits_totals_evenly_and_exactly():
    vms = generate_vms(10, 100, 500.0, 5000.0, "Primary")

    assert len(vms) == 10
    assert sum(v.vcpu for v in vms) == 100
    assert sum(v.ram_gb for v in vms) == 500.0
    assert sum(v.disk_gb for v in vms) == 5000.0
    assert all(v.site == "Primary" for v in vms)


def test_generate_vms_uneven_split_still_sums_exactly():
    vms = generate_vms(3, 10, 30.0, 300.0, "Primary")

    assert sum(v.vcpu for v in vms) == 10
    assert max(v.vcpu for v in vms) - min(v.vcpu for v in vms) <= 1


def test_generate_vms_names_are_generic_and_sequential():
    vms = generate_vms(3, 30, 90.0, 900.0, "Primary")

    assert [v.name for v in vms] == ["vm-01", "vm-02", "vm-03"]


def test_generate_vms_zero_count_returns_empty():
    assert generate_vms(0, 100, 500, 5000, "Primary") == []


# ----------------------------------------------------------------------
# NewProjectWizardDialog
# ----------------------------------------------------------------------

def test_default_site_selection_is_primary_and_dr():
    dialog = NewProjectWizardDialog()

    assert dialog.get_site_names() == ["Primary", "DR"]


def test_primary_only_selection():
    dialog = NewProjectWizardDialog()
    dialog.sites_primary_only.setChecked(True)

    assert dialog.get_site_names() == ["Primary"]


def test_primary_dr_plus_more_sites():
    dialog = NewProjectWizardDialog()
    dialog.sites_primary_dr_more.setChecked(True)
    dialog.extra_sites_spin.setValue(2)

    assert dialog.get_site_names() == ["Primary", "DR", "DR2", "DR3"]


def test_hypervisor_defaults_to_skip():
    dialog = NewProjectWizardDialog()

    assert dialog.get_hypervisor_preset_key() is None


def test_hypervisor_selection_returns_preset_key():
    dialog = NewProjectWizardDialog()
    dialog.hypervisor_combo.setCurrentIndex(1)

    assert dialog.get_hypervisor_preset_key() is not None


def test_vm_params_none_when_count_is_zero():
    dialog = NewProjectWizardDialog()

    assert dialog.get_vm_generation_params() is None


def test_vm_params_returned_when_count_set():
    dialog = NewProjectWizardDialog()
    dialog.vm_count_spin.setValue(10)
    dialog.total_vcpu_spin.setValue(100)
    dialog.total_ram_spin.setValue(500)
    dialog.total_disk_spin.setValue(5000)

    assert dialog.get_vm_generation_params() == (10, 100, 500.0, 5000.0)


def test_navigation_through_all_pages():
    dialog = NewProjectWizardDialog()
    assert dialog.stack.currentIndex() == 0
    assert dialog.back_button.isEnabled() is False

    dialog._go_next()
    assert dialog.stack.currentIndex() == 1
    assert dialog.back_button.isEnabled() is True
    assert dialog.next_button.text() == "Next"

    dialog._go_next()
    assert dialog.stack.currentIndex() == 2
    assert dialog.next_button.text() == "Next"

    dialog._go_next()
    assert dialog.stack.currentIndex() == 3
    assert dialog.next_button.text() == "Finish"

    dialog._go_back()
    assert dialog.stack.currentIndex() == 2


def _mock_dialog(sites, preset_key, server_params, vm_params):
    m = type("MockDialog", (), {})()
    m.exec = lambda: True
    m.get_site_names = lambda: sites
    m.get_hypervisor_preset_key = lambda: preset_key
    m.get_server_generation_params = lambda: server_params
    m.get_vm_generation_params = lambda: vm_params
    return m


def test_wizard_applies_sites_preset_and_generates_vms():
    service = ProjectService()
    window = MainWindow(service)
    mock = _mock_dialog(["Primary", "DR", "DR2"], "vmware", None, (10, 100, 500.0, 5000.0))

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert service.project.site_names == ["Primary", "DR", "DR2"]
    assert service.thresholds.cpu_warning_ratio == 3.0
    assert len(service.project.vms) == 10
    assert sum(v.vcpu for v in service.project.vms) == 100


def test_wizard_primary_only_removes_dr():
    service = ProjectService()
    window = MainWindow(service)
    mock = _mock_dialog(["Primary"], None, None, None)

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert service.project.site_names == ["Primary"]
    assert service.project.vms == []


def test_wizard_cancel_leaves_project_untouched():
    service = ProjectService()
    service.project.name = "Untouched"
    window = MainWindow(service)
    mock = type("MockDialog", (), {"exec": lambda self: False})()

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert service.project.name == "Untouched"


def test_wizard_skip_hypervisor_leaves_default_thresholds():
    service = ProjectService()
    default_cpu_warning = service.thresholds.cpu_warning_ratio
    window = MainWindow(service)
    mock = _mock_dialog(["Primary", "DR"], None, None, None)

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert service.thresholds.cpu_warning_ratio == default_cpu_warning


# ----------------------------------------------------------------------
# generate_servers - pure calculation
# ----------------------------------------------------------------------

def test_generate_servers_creates_identical_servers():
    from src.calculations.vm_generation import generate_servers

    servers = generate_servers(3, 2, 24, 512, "Primary")

    assert len(servers) == 3
    assert all(s.sockets == 2 for s in servers)
    assert all(s.cores_per_socket == 24 for s in servers)
    assert all(s.ram_gb == 512 for s in servers)
    assert all(s.site == "Primary" for s in servers)


def test_generate_servers_names_are_sequential():
    from src.calculations.vm_generation import generate_servers

    servers = generate_servers(3, 2, 16, 256, "Primary")

    assert [s.name for s in servers] == ["server-01", "server-02", "server-03"]


def test_generate_servers_zero_count_returns_empty():
    from src.calculations.vm_generation import generate_servers

    assert generate_servers(0, 2, 16, 256, "Primary") == []


# ----------------------------------------------------------------------
# NewProjectWizardDialog - Servers page
# ----------------------------------------------------------------------

def test_wizard_has_four_pages_including_servers():
    dialog = NewProjectWizardDialog()

    assert dialog.stack.count() == 4


def test_server_params_none_when_count_is_zero():
    dialog = NewProjectWizardDialog()

    assert dialog.get_server_generation_params() is None


def test_server_params_returned_when_count_set():
    dialog = NewProjectWizardDialog()
    dialog.server_count_spin.setValue(3)
    dialog.server_sockets_spin.setValue(2)
    dialog.server_cores_spin.setValue(24)
    dialog.server_ram_spin.setValue(512)

    assert dialog.get_server_generation_params() == (3, 2, 24, 512)


def test_server_specs_disabled_until_count_set():
    dialog = NewProjectWizardDialog()

    assert dialog.server_sockets_spin.isEnabled() is False

    dialog.server_count_spin.setValue(5)

    assert dialog.server_sockets_spin.isEnabled() is True


def test_wizard_dialog_has_a_fixed_reasonable_size():
    """Reported directly: the wizard window appeared oddly positioned
    and couldn't be resized/adjusted - made it a small fixed size
    instead of a resizable-but-broken one."""
    dialog = NewProjectWizardDialog()

    assert dialog.size().width() <= 500
    assert dialog.size().height() <= 400


# ----------------------------------------------------------------------
# Full MainWindow integration - Servers + VMs together
# ----------------------------------------------------------------------

def test_wizard_generates_both_servers_and_vms():
    service = ProjectService()
    window = MainWindow(service)
    mock = _mock_dialog(
        ["Primary", "DR"], "vmware", (3, 2, 24, 512), (10, 100, 500.0, 5000.0),
    )

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert len(service.project.servers) == 3
    assert service.project.servers[0].sockets == 2
    assert service.project.servers[0].cores_per_socket == 24
    assert len(service.project.vms) == 10


def test_wizard_skip_servers_generates_only_vms():
    service = ProjectService()
    window = MainWindow(service)
    mock = _mock_dialog(["Primary", "DR"], None, None, (5, 20, 100.0, 1000.0))

    with patch("src.gui.main_window.NewProjectWizardDialog", return_value=mock):
        window._new_project_with_wizard()

    assert service.project.servers == []
    assert len(service.project.vms) == 5
