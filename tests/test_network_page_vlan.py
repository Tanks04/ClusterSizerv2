"""Real Qt tests for the VLANs section of NetworkPage."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.gui.pages.network_page import NetworkPage
from src.models.vlan import Vlan
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_vlan_table_is_empty_initially():
    service = ProjectService()
    page = NetworkPage(service)

    assert page.vlan_model.rowCount() == 0


def test_adding_a_vlan_via_service_refreshes_the_table():
    service = ProjectService()
    page = NetworkPage(service)

    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    service.add_vlan(vlan)

    assert page.vlan_model.rowCount() == 1
    assert page.vlan_model.vlan_at(0).name == "DMZ"


def test_vm_count_column_updates_when_a_vm_is_assigned():
    service = ProjectService()
    page = NetworkPage(service)

    vlan = Vlan.create_default()
    service.add_vlan(vlan)
    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid
    service.add_vm(vm)  # fires vms_changed -> page.refresh(), which the page listens to

    from PySide6.QtCore import Qt
    index = page.vlan_model.index(0, 4)
    assert page.vlan_model.data(index, Qt.ItemDataRole.DisplayRole) == "1"


def test_deleting_selected_vlans_removes_them():
    service = ProjectService()
    page = NetworkPage(service)
    vlan = Vlan.create_default()
    service.add_vlan(vlan)

    service.remove_vlans([vlan])

    assert page.vlan_model.rowCount() == 0
