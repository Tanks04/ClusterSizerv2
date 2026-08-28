"""Real Qt tests for ProjectService's VLAN CRUD - QObject-based, needs
PySide6, as elsewhere in this project."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.services.project_service import ProjectService
from src.models.vlan import Vlan
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_add_vlan():
    service = ProjectService()
    vlan = Vlan.create_default()
    vlan.name = "DMZ"

    service.add_vlan(vlan)

    assert len(service.project.vlans) == 1
    assert service.project.vlans[0].name == "DMZ"


def test_update_vlan():
    service = ProjectService()
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    service.add_vlan(vlan)

    updated = Vlan.create_default()
    updated.uid = vlan.uid
    updated.name = "Renamed"
    service.update_vlan(0, updated)

    assert service.project.vlans[0].name == "Renamed"


def test_remove_vlans_clears_vm_references():
    service = ProjectService()
    vlan = Vlan.create_default()
    service.add_vlan(vlan)
    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid
    service.add_vm(vm)

    service.remove_vlans([vlan])

    assert service.project.vlans == []
    assert service.project.vms[0].vlan_uid == ""


def test_remove_vlans_does_not_delete_the_vm_itself():
    service = ProjectService()
    vlan = Vlan.create_default()
    service.add_vlan(vlan)
    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid
    service.add_vm(vm)

    service.remove_vlans([vlan])

    assert len(service.project.vms) == 1


def test_clear_vlans_clears_all_vm_references():
    service = ProjectService()
    vlan1 = Vlan.create_default()
    vlan2 = Vlan.create_default()
    service.add_vlan(vlan1)
    service.add_vlan(vlan2)
    vm1 = VirtualMachine.create_default()
    vm1.vlan_uid = vlan1.uid
    vm2 = VirtualMachine.create_default()
    vm2.vlan_uid = vlan2.uid
    service.add_vm(vm1)
    service.add_vm(vm2)

    service.clear_vlans()

    assert service.project.vlans == []
    assert all(vm.vlan_uid == "" for vm in service.project.vms)


def test_undo_restores_vlan_and_vm_reference():
    service = ProjectService()
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    service.add_vlan(vlan)
    vm = VirtualMachine.create_default()
    vm.vlan_uid = vlan.uid
    service.add_vm(vm)

    service.remove_vlans([vlan])
    assert service.project.vms[0].vlan_uid == ""

    service.undo()

    assert service.project.vlans[0].name == "DMZ"
    assert service.project.vms[0].vlan_uid == vlan.uid


def test_import_export_vlans_csv(tmp_path):
    service = ProjectService()
    vlan = Vlan.create_default()
    vlan.name = "DMZ"
    vlan.network = "10.0.0.0/24"
    service.add_vlan(vlan)

    path = tmp_path / "vlans.csv"
    service.export_vlans_csv(path)

    service2 = ProjectService()
    count = service2.import_vlans_csv(path)

    assert count == 1
    assert service2.project.vlans[0].name == "DMZ"
    assert service2.project.vlans[0].network == "10.0.0.0/24"
