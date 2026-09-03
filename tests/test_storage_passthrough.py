"""Tests for PCI passthrough storage pools - the opposite assignment
direction from a normal pool (zoned to hosts): wired directly to ONE
VM, bypassing the hypervisor/cluster entirely. Requested directly with
a concrete example (security VM with two passthrough disk groups,
Sec_data_os and Sec_data_log) plus a request to visually highlight any
VM that has one.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.models.server import Server
from src.models.storage import Storage, StoragePool
from src.models.virtual_machine import VirtualMachine


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# StoragePool model
# ----------------------------------------------------------------------

def test_pool_defaults_to_not_passthrough():
    pool = StoragePool(uid="p1", name="SSD-Tier")

    assert pool.is_passthrough is False
    assert pool.passthrough_vm_uid == ""


def test_pool_can_be_marked_passthrough_with_a_connected_vm():
    pool = StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid="vm-123")

    assert pool.is_passthrough is True
    assert pool.passthrough_vm_uid == "vm-123"


def test_passthrough_fields_clsz_round_trip(tmp_path):
    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.persistence import project_repository

    project = ClusterProject(name="Passthrough round trip")
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid="vm-123")
    storage.pools = [pool]
    project.storages.append(storage)

    path = tmp_path / "pt.clsz"
    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].pools[0].is_passthrough is True
    assert loaded.project.storages[0].pools[0].passthrough_vm_uid == "vm-123"


def test_old_clsz_file_without_passthrough_fields_defaults_gracefully(tmp_path):
    import json

    from src.calculations.thresholds import Thresholds
    from src.models.cluster_project import ClusterProject
    from src.persistence import project_repository

    project = ClusterProject(name="Pre-passthrough")
    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Plain")]
    project.storages.append(storage)
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["storages"][0]["pools"][0]["is_passthrough"]
    del raw["storages"][0]["pools"][0]["passthrough_vm_uid"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    assert loaded.project.storages[0].pools[0].is_passthrough is False
    assert loaded.project.storages[0].pools[0].passthrough_vm_uid == ""


# ----------------------------------------------------------------------
# StoragePoolDialog - passthrough checkbox + VM picker
# ----------------------------------------------------------------------

def test_vm_combo_hidden_by_default():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()

    assert dialog.form_layout.isRowVisible(dialog.passthrough_vm_combo) is False
    assert dialog.form_layout.isRowVisible(dialog._servers_box) is True


def test_checking_passthrough_swaps_visible_sections():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()

    dialog.passthrough_check.setChecked(True)

    assert dialog.form_layout.isRowVisible(dialog.passthrough_vm_combo) is True
    assert dialog.form_layout.isRowVisible(dialog._servers_box) is False


def test_unchecking_passthrough_restores_servers_section():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()
    dialog.passthrough_check.setChecked(True)

    dialog.passthrough_check.setChecked(False)

    assert dialog.form_layout.isRowVisible(dialog.passthrough_vm_combo) is False
    assert dialog.form_layout.isRowVisible(dialog._servers_box) is True


def test_vm_combo_lists_the_given_vms():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    vm1 = VirtualMachine.create_default()
    vm1.name = "security-vm"
    vm2 = VirtualMachine.create_default()
    vm2.name = "web-vm"

    dialog = StoragePoolDialog(vms=[vm1, vm2])

    items = [dialog.passthrough_vm_combo.itemText(i) for i in range(dialog.passthrough_vm_combo.count())]
    assert any("security-vm" in i for i in items)
    assert any("web-vm" in i for i in items)


def test_saving_a_passthrough_pool_with_connected_vm():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    vm = VirtualMachine.create_default()
    vm.name = "security-vm"
    dialog = StoragePoolDialog(vms=[vm])
    dialog.name_edit.setText("Sec_data_os")
    dialog.passthrough_check.setChecked(True)
    dialog.passthrough_vm_combo.setCurrentIndex(dialog.passthrough_vm_combo.findData(vm.uid))

    pool = dialog.get_pool()

    assert pool.is_passthrough is True
    assert pool.passthrough_vm_uid == vm.uid


def test_non_passthrough_pool_saves_empty_vm_uid():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StoragePoolDialog()
    dialog.name_edit.setText("Regular-Pool")

    pool = dialog.get_pool()

    assert pool.is_passthrough is False
    assert pool.passthrough_vm_uid == ""


def test_editing_an_existing_passthrough_pool_loads_correctly():
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    vm = VirtualMachine.create_default()
    vm.name = "security-vm"
    existing = StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid=vm.uid)

    dialog = StoragePoolDialog(existing, vms=[vm])

    assert dialog.passthrough_check.isChecked() is True
    assert dialog.passthrough_vm_combo.currentData() == vm.uid
    assert dialog.form_layout.isRowVisible(dialog.passthrough_vm_combo) is True


def test_storage_dialog_passes_project_vms_to_pool_dialog():
    from src.gui.dialogs.storage_dialog import StorageDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog
    from src.services.project_service import ProjectService

    service = ProjectService()
    vm = VirtualMachine.create_default()
    vm.name = "security-vm"
    service.add_vm(vm)
    dialog = StorageDialog(servers=[], service=service)
    new_pool = StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid=vm.uid)

    with patch.object(StoragePoolDialog, "exec", return_value=True), \
         patch.object(StoragePoolDialog, "get_pool", return_value=new_pool):
        dialog._add_pool()

    storage = dialog.get_storage()
    assert storage.pools[0].is_passthrough is True
    assert storage.pools[0].passthrough_vm_uid == vm.uid


def test_storage_dialog_without_service_passes_empty_vm_list():
    from src.gui.dialogs.storage_dialog import StorageDialog
    from src.gui.dialogs.storage_pool_dialog import StoragePoolDialog

    dialog = StorageDialog(servers=[])

    with patch.object(StoragePoolDialog, "__init__", return_value=None) as mock_init, \
         patch.object(StoragePoolDialog, "exec", return_value=False):
        dialog._add_pool()

    _, kwargs = mock_init.call_args
    assert kwargs["vms"] == []


# ----------------------------------------------------------------------
# VM table - colored border for VMs with passthrough storage
# ----------------------------------------------------------------------

def test_vm_with_passthrough_pool_gets_a_border_color():
    from src.gui.models.vm_table_model import (
        PASSTHROUGH_BORDER_COLOR_ROLE,
        VMTableModel,
    )

    vm = VirtualMachine.create_default()
    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid=vm.uid)]
    model = VMTableModel([vm], storages_provider=lambda: [storage])

    color = model.data(model.index(0, 0), PASSTHROUGH_BORDER_COLOR_ROLE)

    assert color is not None


def test_vm_without_passthrough_pool_gets_no_border():
    from src.gui.models.vm_table_model import (
        PASSTHROUGH_BORDER_COLOR_ROLE,
        VMTableModel,
    )

    vm = VirtualMachine.create_default()
    model = VMTableModel([vm], storages_provider=lambda: [])

    color = model.data(model.index(0, 0), PASSTHROUGH_BORDER_COLOR_ROLE)

    assert color is None


def test_regular_pool_assignment_does_not_trigger_border():
    """Just being assigned to an ordinary pool (storage_pool_uid) is
    NOT the same as having a passthrough pool connected - only
    is_passthrough + passthrough_vm_uid matching should highlight."""
    from src.gui.models.vm_table_model import (
        PASSTHROUGH_BORDER_COLOR_ROLE,
        VMTableModel,
    )

    vm = VirtualMachine.create_default()
    storage = Storage.create_default()
    pool = StoragePool(uid="p1", name="VM_data")  # not passthrough
    storage.pools = [pool]
    vm.storage_uid = storage.uid
    vm.storage_pool_uid = pool.uid
    model = VMTableModel([vm], storages_provider=lambda: [storage])

    color = model.data(model.index(0, 0), PASSTHROUGH_BORDER_COLOR_ROLE)

    assert color is None


def test_two_different_vms_each_with_their_own_passthrough_pool():
    from src.gui.models.vm_table_model import (
        PASSTHROUGH_BORDER_COLOR_ROLE,
        VMTableModel,
    )

    vm1 = VirtualMachine.create_default()
    vm2 = VirtualMachine.create_default()
    storage = Storage.create_default()
    storage.pools = [
        StoragePool(uid="p1", name="A", is_passthrough=True, passthrough_vm_uid=vm1.uid),
        StoragePool(uid="p2", name="B", is_passthrough=True, passthrough_vm_uid=vm2.uid),
    ]
    model = VMTableModel([vm1, vm2], storages_provider=lambda: [storage])

    assert model.data(model.index(0, 0), PASSTHROUGH_BORDER_COLOR_ROLE) is not None
    assert model.data(model.index(1, 0), PASSTHROUGH_BORDER_COLOR_ROLE) is not None


def test_vm_with_two_passthrough_pools_still_gets_one_border():
    """The exact reported scenario: one VM connected to BOTH
    Sec_data_os and Sec_data_log."""
    from src.gui.models.vm_table_model import (
        PASSTHROUGH_BORDER_COLOR_ROLE,
        VMTableModel,
    )

    vm = VirtualMachine.create_default()
    storage = Storage.create_default()
    storage.pools = [
        StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid=vm.uid),
        StoragePool(uid="p2", name="Sec_data_log", is_passthrough=True, passthrough_vm_uid=vm.uid),
    ]
    model = VMTableModel([vm], storages_provider=lambda: [storage])

    color = model.data(model.index(0, 0), PASSTHROUGH_BORDER_COLOR_ROLE)

    assert color is not None


def test_delegate_paints_a_border_for_passthrough_vms():
    from src.gui.models.vm_table_model import VMTableModel
    from src.gui.widgets.passthrough_border_delegate import PassthroughBorderDelegate

    vm = VirtualMachine.create_default()
    storage = Storage.create_default()
    storage.pools = [StoragePool(uid="p1", name="Sec_data_os", is_passthrough=True, passthrough_vm_uid=vm.uid)]
    model = VMTableModel([vm], storages_provider=lambda: [storage])
    delegate = PassthroughBorderDelegate()

    # Smoke test: paint() must not raise when given a real index with
    # a border color set - actual pixel rendering is covered by the
    # visual screenshot check done during development.
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem
    pixmap = QPixmap(100, 20)
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    delegate.paint(painter, option, model.index(0, 0))
    painter.end()
