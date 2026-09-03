"""Real Qt tests for the generalized import-conflict (Add/Replace/
Cancel) prompt - generalizes the pattern already established for
Cluster Preparation's per-site Add button to every CSV import in the
app: if the destination already has some of this kind of entity, ask
before silently appending on top of it."""

import csv
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from src.gui.import_conflict import ImportConflictChoice, confirm_import_conflict
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.storage import Storage
from src.models.virtual_machine import VirtualMachine
from src.models.vlan import Vlan
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# The shared helper itself
# ----------------------------------------------------------------------

def test_no_prompt_when_nothing_exists():
    with patch.object(QMessageBox, "question") as mock_question:
        choice = confirm_import_conflict(None, "server", 0, 5)

    assert choice == ImportConflictChoice.ADD
    assert not mock_question.called


def test_yes_returns_add():
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        choice = confirm_import_conflict(None, "server", 3, 5)

    assert choice == ImportConflictChoice.ADD


def test_no_returns_replace():
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        choice = confirm_import_conflict(None, "server", 3, 5)

    assert choice == ImportConflictChoice.REPLACE


def test_cancel_returns_cancel():
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
        choice = confirm_import_conflict(None, "server", 3, 5)

    assert choice == ImportConflictChoice.CANCEL


# ----------------------------------------------------------------------
# ProjectService's import_*_csv methods accept replace=
# ----------------------------------------------------------------------

def test_import_servers_csv_replace_true_clears_existing(tmp_path):
    service = ProjectService()
    service.add_server(Server.create_default())
    path = tmp_path / "s.csv"
    path.write_text("name,site,sockets,cores_per_socket\nnew,Primary,2,16\n", encoding="utf-8")

    service.import_servers_csv(path, replace=True)

    assert len(service.project.servers) == 1
    assert service.project.servers[0].name == "new"


def test_import_servers_csv_replace_false_extends(tmp_path):
    service = ProjectService()
    service.add_server(Server.create_default())
    path = tmp_path / "s.csv"
    path.write_text("name,site,sockets,cores_per_socket\nnew,Primary,2,16\n", encoding="utf-8")

    service.import_servers_csv(path, replace=False)

    assert len(service.project.servers) == 2


def test_import_servers_csv_defaults_to_extend_for_backward_compat(tmp_path):
    """Old callers of import_servers_csv(path) with no replace argument
    must keep working exactly as before this feature existed."""
    service = ProjectService()
    service.add_server(Server.create_default())
    path = tmp_path / "s.csv"
    path.write_text("name,site,sockets,cores_per_socket\nnew,Primary,2,16\n", encoding="utf-8")

    service.import_servers_csv(path)

    assert len(service.project.servers) == 2


# ----------------------------------------------------------------------
# Full GUI flow across every page - Add and Replace both actually work
# ----------------------------------------------------------------------

def _write_csv(path, header, row):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(row)


def test_servers_page_add_choice(tmp_path):
    from src.gui.pages.servers_page import ServersPage

    service = ProjectService()
    service.add_server(Server.create_default())
    page = ServersPage(service)
    path = tmp_path / "s.csv"
    _write_csv(path, ["name", "site", "sockets", "cores_per_socket"], ["new", "Primary", "2", "16"])

    with patch("src.gui.pages.servers_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.servers) == 2


def test_servers_page_replace_choice(tmp_path):
    from src.gui.pages.servers_page import ServersPage

    service = ProjectService()
    service.add_server(Server.create_default())
    page = ServersPage(service)
    path = tmp_path / "s.csv"
    _write_csv(path, ["name", "site", "sockets", "cores_per_socket"], ["new", "Primary", "2", "16"])

    with patch("src.gui.pages.servers_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.servers) == 1
    assert service.project.servers[0].name == "new"


def test_servers_page_cancel_choice_imports_nothing(tmp_path):
    from src.gui.pages.servers_page import ServersPage

    service = ProjectService()
    existing = Server.create_default()
    service.add_server(existing)
    page = ServersPage(service)
    path = tmp_path / "s.csv"
    _write_csv(path, ["name", "site", "sockets", "cores_per_socket"], ["new", "Primary", "2", "16"])

    with patch("src.gui.pages.servers_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
        page._import_csv()

    assert len(service.project.servers) == 1
    assert service.project.servers[0].uid == existing.uid


def test_storage_page_replace_choice(tmp_path):
    from src.gui.pages.storage_page import StoragePage

    service = ProjectService()
    service.add_storage(Storage.create_default())
    page = StoragePage(service)
    path = tmp_path / "st.csv"
    _write_csv(path, ["name", "site", "raw_capacity_tb", "usable_capacity_tb"], ["new", "Primary", "10", "8"])

    with patch("src.gui.pages.storage_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.storages) == 1
    assert service.project.storages[0].name == "new"


def test_vms_page_replace_choice(tmp_path):
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())
    page = VirtualMachinesPage(service)
    path = tmp_path / "vm.csv"
    _write_csv(path, ["name", "site", "vcpu", "ram_gb", "disk_gb"], ["new", "Primary", "4", "16", "100"])

    with patch("src.gui.pages.virtual_machines_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.vms) == 1
    assert service.project.vms[0].name == "new"


def test_backup_page_replace_choice(tmp_path):
    from src.gui.pages.backup_page import BackupPage

    service = ProjectService()
    service.add_backup_destination(BackupDestination.create_default())
    page = BackupPage(service)
    path = tmp_path / "bk.csv"
    _write_csv(path, ["name", "site", "destination_type", "backup_software"], ["new", "Primary", "NAS", "Veeam"])

    with patch("src.gui.pages.backup_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.backup_destinations) == 1
    assert service.project.backup_destinations[0].name == "new"


def test_pricing_page_replace_choice(tmp_path):
    from src.gui.pages.pricing_page import PricingPage

    service = ProjectService()
    service.add_maintenance_item(MaintenanceItem.create_default())
    page = PricingPage(service)
    path = tmp_path / "mi.csv"
    _write_csv(path, ["name", "category", "cost", "duration_months"], ["new", "License", "100", "12"])

    with patch("src.gui.pages.pricing_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_csv()

    assert len(service.project.maintenance_items) == 1
    assert service.project.maintenance_items[0].name == "new"


def test_network_page_switches_replace_choice(tmp_path):
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    service.add_switch(NetworkSwitch.create_default())
    page = NetworkPage(service)
    path = tmp_path / "sw.csv"
    _write_csv(path, ["name", "site", "switch_type"], ["new", "Primary", "LAN"])

    with patch("src.gui.pages.network_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_switches_csv()

    assert len(service.project.switches) == 1
    assert service.project.switches[0].name == "new"


def test_network_page_vlans_replace_choice(tmp_path):
    from src.gui.pages.network_page import NetworkPage

    service = ProjectService()
    service.add_vlan(Vlan.create_default())
    page = NetworkPage(service)
    path = tmp_path / "vl.csv"
    _write_csv(path, ["name", "site", "network"], ["new", "Primary", "10.0.0.0/24"])

    with patch("src.gui.pages.network_page.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._import_vlans_csv()

    assert len(service.project.vlans) == 1
    assert service.project.vlans[0].name == "new"


# ----------------------------------------------------------------------
# add_vms(replace=) and add_servers_and_vms(replace=) - cascade cleanup
# ----------------------------------------------------------------------

def test_add_vms_replace_cascades_failover_assignment_cleanup():
    from src.models.failover_assignment import FailoverAssignment

    service = ProjectService()
    existing_vm = VirtualMachine.create_default()
    service.add_vm(existing_vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = existing_vm.uid
    assignment.target_site = "DR"
    service.add_failover_assignment(assignment)

    new_vm = VirtualMachine.create_default()
    service.add_vms([new_vm], replace=True)

    assert len(service.project.vms) == 1
    assert service.project.vms[0].uid == new_vm.uid
    assert service.project.failover_assignments == []


def test_add_vms_default_extends_not_replaces():
    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())

    service.add_vms([VirtualMachine.create_default()])

    assert len(service.project.vms) == 2


def test_add_servers_and_vms_replace_cascades_failover_cleanup():
    from src.models.failover_assignment import FailoverAssignment

    service = ProjectService()
    existing_server = Server.create_default()
    existing_vm = VirtualMachine.create_default()
    service.add_server(existing_server)
    service.add_vm(existing_vm)
    assignment = FailoverAssignment.create_default()
    assignment.vm_uid = existing_vm.uid
    assignment.target_site = "DR"
    service.add_failover_assignment(assignment)

    service.add_servers_and_vms([Server.create_default()], [VirtualMachine.create_default()], replace=True)

    assert len(service.project.servers) == 1
    assert len(service.project.vms) == 1
    assert service.project.failover_assignments == []


def test_add_servers_and_vms_default_extends():
    service = ProjectService()
    service.add_server(Server.create_default())

    service.add_servers_and_vms([Server.create_default()], [VirtualMachine.create_default()])

    assert len(service.project.servers) == 2


def test_smart_import_replace_choice(tmp_path):
    """Smart Import (RVTools/VMware/Nutanix/Proxmox via ImportWizardDialog)
    gets the same conflict prompt as CSV imports."""
    from unittest.mock import MagicMock

    from src.gui.dialogs.import_wizard_dialog import ImportWizardDialog
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    service.add_vm(VirtualMachine.create_default())
    page = VirtualMachinesPage(service)

    new_vm = VirtualMachine.create_default()
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1
    mock_dialog.get_imported_vms.return_value = [new_vm]
    mock_dialog.get_skipped_count.return_value = 0

    fake_path = tmp_path / "export.csv"
    fake_path.write_text("dummy", encoding="utf-8")

    with patch("src.gui.pages.virtual_machines_page.QFileDialog.getOpenFileName", return_value=(str(fake_path), "")), \
         patch("src.gui.pages.virtual_machines_page.ImportWizardDialog", return_value=mock_dialog), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        page._smart_import()

    assert len(service.project.vms) == 1
    assert service.project.vms[0].uid == new_vm.uid


def test_rvtools_import_replace_choice():
    from unittest.mock import MagicMock

    from src.gui.dialogs.rvtools_import_dialog import RVToolsImportDialog
    from src.gui.main_window import MainWindow

    service = ProjectService()
    service.add_server(Server.create_default())
    window = MainWindow(service)

    new_server = Server.create_default()
    new_vm = VirtualMachine.create_default()
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1
    mock_dialog.get_servers.return_value = [new_server]
    mock_dialog.get_vms.return_value = [new_vm]
    mock_dialog.get_switches.return_value = []

    with patch("src.gui.main_window.RVToolsImportDialog", return_value=mock_dialog), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, "information"):
        window._import_rvtools()

    assert len(service.project.servers) == 1
    assert service.project.servers[0].uid == new_server.uid


def test_rvtools_import_cancel_choice_imports_nothing():
    from unittest.mock import MagicMock

    from src.gui.dialogs.rvtools_import_dialog import RVToolsImportDialog
    from src.gui.main_window import MainWindow

    service = ProjectService()
    existing = Server.create_default()
    service.add_server(existing)
    window = MainWindow(service)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1
    mock_dialog.get_servers.return_value = [Server.create_default()]
    mock_dialog.get_vms.return_value = [VirtualMachine.create_default()]
    mock_dialog.get_switches.return_value = []

    with patch("src.gui.main_window.RVToolsImportDialog", return_value=mock_dialog), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
        window._import_rvtools()

    assert len(service.project.servers) == 1
    assert service.project.servers[0].uid == existing.uid
