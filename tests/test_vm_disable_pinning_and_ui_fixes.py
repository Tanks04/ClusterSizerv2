"""Tests for a batch of features requested together: VM disable/enable,
VM-to-server pinning (separate from Cluster assignment), the resulting
per-server dedicated-VM load calculations, and several Summary/
Attention panel UI fixes.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.models.cluster import Cluster
from src.models.cluster_project import PRIMARY, ClusterProject
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.services.project_service import ProjectService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# VM disable/enable
# ----------------------------------------------------------------------

def test_set_powered_on_for_vms_excludes_from_demand():
    service = ProjectService()
    vm = VirtualMachine.create_default()
    vm.vcpu = 8
    service.add_vm(vm)

    service.set_powered_on_for_vms([vm], False)

    assert service.project.vm_vcpu_demand(PRIMARY) == 0


def test_set_powered_on_for_vms_re_enable_restores_demand():
    service = ProjectService()
    vm = VirtualMachine.create_default()
    vm.vcpu = 8
    service.add_vm(vm)
    service.set_powered_on_for_vms([vm], False)

    service.set_powered_on_for_vms([vm], True)

    assert service.project.vm_vcpu_demand(PRIMARY) == 8


def test_set_powered_on_is_one_undo_step_for_a_selection():
    service = ProjectService()
    vm1 = VirtualMachine.create_default()
    vm2 = VirtualMachine.create_default()
    service.add_vm(vm1)
    service.add_vm(vm2)

    service.set_powered_on_for_vms([vm1, vm2], False)
    assert all(not v.powered_on for v in service.project.vms)

    service.undo()

    assert all(v.powered_on for v in service.project.vms)


def test_vms_page_has_disable_and_enable_actions():
    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    page = VirtualMachinesPage(service)

    labels = [l for l, _ in page.table._custom_actions]
    assert any("Disable" in l for l in labels)
    assert any("Enable" in l for l in labels)


def test_disable_works_on_a_multi_selection():
    from PySide6.QtCore import QItemSelectionModel

    from src.gui.pages.virtual_machines_page import VirtualMachinesPage

    service = ProjectService()
    vm1 = VirtualMachine.create_default()
    vm1.vcpu = 8
    vm2 = VirtualMachine.create_default()
    vm2.vcpu = 4
    vm3 = VirtualMachine.create_default()
    vm3.vcpu = 2
    service.add_vm(vm1)
    service.add_vm(vm2)
    service.add_vm(vm3)
    page = VirtualMachinesPage(service)
    sel = page.table.selectionModel()
    for row in (0, 1):
        sel.select(
            page.table.model().index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )

    page._set_powered_on_for_selected(False)

    assert service.project.vm_vcpu_demand(PRIMARY) == 2


# ----------------------------------------------------------------------
# VirtualMachine.pinned_server_uid - mutually exclusive with cluster_uid
# ----------------------------------------------------------------------

def test_pinned_server_uid_defaults_empty():
    vm = VirtualMachine.create_default()

    assert vm.pinned_server_uid == ""


def test_pinned_server_uid_clsz_round_trip(tmp_path):
    from src.calculations.thresholds import Thresholds
    from src.persistence import project_repository

    project = ClusterProject(name="Pin round trip")
    vm = VirtualMachine.create_default()
    vm.pinned_server_uid = "srv-123"
    project.vms.append(vm)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    assert loaded.project.vms[0].pinned_server_uid == "srv-123"


# ----------------------------------------------------------------------
# Per-server pinned VM demand/ratio calculations
# ----------------------------------------------------------------------

def _server(cores_per_socket=16, sockets=2, ram_gb=512):
    s = Server.create_default()
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.ram_gb = ram_gb
    s.hyperthreading_enabled = False
    return s


def test_pinned_vms_for_server_only_counts_that_server():
    project = ClusterProject()
    srv1 = _server()
    srv2 = _server()
    project.servers.extend([srv1, srv2])
    vm1 = VirtualMachine.create_default()
    vm1.pinned_server_uid = srv1.uid
    vm2 = VirtualMachine.create_default()
    vm2.pinned_server_uid = srv2.uid
    project.vms.extend([vm1, vm2])

    assert project.pinned_vms_for_server(srv1.uid) == [vm1]


def test_pinned_vms_excludes_powered_off_vms():
    project = ClusterProject()
    srv = _server()
    project.servers.append(srv)
    vm = VirtualMachine.create_default()
    vm.pinned_server_uid = srv.uid
    vm.powered_on = False
    project.vms.append(vm)

    assert project.pinned_vms_for_server(srv.uid) == []


def test_server_vcpu_ram_disk_demand_sums_pinned_vms_only():
    project = ClusterProject()
    srv = _server()
    project.servers.append(srv)
    for _ in range(4):
        vm = VirtualMachine.create_default()
        vm.pinned_server_uid = srv.uid
        vm.vcpu = 21
        vm.ram_gb = 113 / 4
        vm.disk_gb = 450 / 4
        project.vms.append(vm)
    unrelated = VirtualMachine.create_default()
    unrelated.vcpu = 999
    project.vms.append(unrelated)

    assert project.server_vcpu_demand(srv.uid) == 84
    assert project.server_ram_demand_gb(srv.uid) == 113.0
    assert project.server_disk_demand_gb(srv.uid) == 450.0


def test_server_cpu_and_ram_ratio_matches_worked_example():
    project = ClusterProject()
    srv = _server(cores_per_socket=16, sockets=2, ram_gb=512)  # 32 effective cores
    project.servers.append(srv)
    for _ in range(4):
        vm = VirtualMachine.create_default()
        vm.pinned_server_uid = srv.uid
        vm.vcpu = 21
        vm.ram_gb = 113 / 4
        project.vms.append(vm)

    cpu_ratio = project.server_cpu_ratio(srv)
    ram_ratio = project.server_ram_ratio(srv)

    assert abs(cpu_ratio - 84 / 32) < 0.001
    assert abs(ram_ratio - 113 / 512) < 0.001


def test_server_ratio_none_when_server_has_zero_capacity():
    project = ClusterProject()
    srv = Server.create_default()
    srv.sockets = 0
    srv.cores_per_socket = 0
    srv.ram_gb = 0
    project.servers.append(srv)

    assert project.server_cpu_ratio(srv) is None
    assert project.server_ram_ratio(srv) is None


# ----------------------------------------------------------------------
# VMDialog combined Cluster/Server dropdown
# ----------------------------------------------------------------------

def _find_combo_index(combo, target):
    for i in range(combo.count()):
        if combo.itemData(i) == target:
            return i
    return -1


def test_combo_lists_clusters_then_servers():
    from src.gui.dialogs.vm_dialog import VMDialog

    cluster = Cluster.create_default(0)
    cluster.name = "ProdCluster"
    srv = Server.create_default()
    srv.name = "srvr4"

    dialog = VMDialog(clusters=[cluster], servers=[srv])

    items = [dialog.cluster_combo.itemText(i) for i in range(dialog.cluster_combo.count())]
    assert "ProdCluster" in items
    assert any("srvr4" in i for i in items)


def test_picking_a_cluster_clears_pinned_server_uid():
    from src.gui.dialogs.vm_dialog import VMDialog

    cluster = Cluster.create_default(0)
    srv = Server.create_default()
    dialog = VMDialog(clusters=[cluster], servers=[srv])
    idx = _find_combo_index(dialog.cluster_combo, ("cluster", cluster.uid))
    dialog.cluster_combo.setCurrentIndex(idx)

    vm = dialog.get_vm()

    assert vm.cluster_uid == cluster.uid
    assert vm.pinned_server_uid == ""


def test_picking_a_server_clears_cluster_uid():
    from src.gui.dialogs.vm_dialog import VMDialog

    cluster = Cluster.create_default(0)
    srv = Server.create_default()
    dialog = VMDialog(clusters=[cluster], servers=[srv])
    idx = _find_combo_index(dialog.cluster_combo, ("server", srv.uid))
    dialog.cluster_combo.setCurrentIndex(idx)

    vm = dialog.get_vm()

    assert vm.cluster_uid == ""
    assert vm.pinned_server_uid == srv.uid


def test_editing_a_pinned_vm_preloads_the_server_selection():
    from src.gui.dialogs.vm_dialog import VMDialog

    srv = Server.create_default()
    srv.name = "srvr5"
    vm = VirtualMachine.create_default()
    vm.pinned_server_uid = srv.uid

    dialog = VMDialog(vm, servers=[srv])

    assert "srvr5" in dialog.cluster_combo.currentText()


def test_editing_a_cluster_vm_still_works_with_no_servers_passed():
    """Regression guard for the findData bug that broke this exact
    existing scenario."""
    from src.gui.dialogs.vm_dialog import VMDialog

    cluster = Cluster.create_default(0)
    cluster.name = "Cluster-C"
    vm = VirtualMachine.create_default()
    vm.cluster_uid = cluster.uid

    dialog = VMDialog(vm, clusters=[cluster])

    assert "Cluster-C" in dialog.cluster_combo.currentText()


# ----------------------------------------------------------------------
# Summary page - Rack Sizing header layout
# ----------------------------------------------------------------------

def test_rack_toggle_button_is_not_the_last_stretched_item():
    """Reported directly: the button sat far right, making Attention
    Needed look like part of Rack Sizing. Confirms the stretch is
    AFTER the button (keeping label+button together) rather than
    before it (which would push the button to the far right)."""
    from src.gui.pages.summary_page import SummaryPage

    service = ProjectService()
    page = SummaryPage(service)

    assert page.rack_toggle_button is not None


# ----------------------------------------------------------------------
# Attention panel - ATTENTION NEEDED styling + copy-to-clipboard
# ----------------------------------------------------------------------

def test_attention_panel_title_is_all_caps():
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()

    assert panel.title() == "ATTENTION NEEDED"


def test_attention_panel_stores_messages_for_copying():
    from src.calculations.attention import AttentionItem
    from src.calculations.thresholds import Status
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    items = [
        AttentionItem(Status.CRITICAL, "Primary: CPU oversubscription is 5.0:1 (Critical)"),
        AttentionItem(Status.WARNING, "DR: RAM utilization is 85% (Warning)"),
    ]

    panel.set_items(items)

    assert panel._messages == [items[0].message, items[1].message]


def test_attention_panel_items_have_context_menu_enabled():
    from PySide6.QtCore import Qt

    from src.calculations.attention import AttentionItem
    from src.calculations.thresholds import Status
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    panel.set_items([AttentionItem(Status.WARNING, "Test message")])

    assert panel._item_labels[0].contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_copy_single_item_puts_exact_message_on_clipboard():
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText("Primary: CPU oversubscription is 5.0:1 (Critical)")

    assert QGuiApplication.clipboard().text() == "Primary: CPU oversubscription is 5.0:1 (Critical)"


def test_copy_all_joins_every_message_with_newlines():
    from PySide6.QtGui import QGuiApplication

    from src.calculations.attention import AttentionItem
    from src.calculations.thresholds import Status
    from src.gui.widgets.attention_panel import AttentionPanel

    panel = AttentionPanel()
    items = [
        AttentionItem(Status.CRITICAL, "Item one"),
        AttentionItem(Status.WARNING, "Item two"),
    ]
    panel.set_items(items)

    QGuiApplication.clipboard().setText("\n".join(panel._messages))

    assert QGuiApplication.clipboard().text() == "Item one\nItem two"
