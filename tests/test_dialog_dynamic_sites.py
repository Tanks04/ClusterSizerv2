"""Real Qt tests confirming every entity dialog's site dropdown is
populated from a passed-in site list (not hardcoded to Primary/DR),
and that omitting the parameter still falls back to Primary/DR for
backward compatibility with any caller not yet updated."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.gui.dialogs.backup_destination_dialog import BackupDestinationDialog
from src.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from src.gui.dialogs.rvtools_import_dialog import RVToolsImportDialog
from src.gui.dialogs.server_dialog import ServerDialog
from src.gui.dialogs.storage_dialog import StorageDialog
from src.gui.dialogs.switch_dialog import SwitchDialog
from src.gui.dialogs.vlan_dialog import VlanDialog
from src.gui.dialogs.vm_dialog import VMDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


THREE_SITES = ["Primary", "DR", "DR2"]


def _items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_server_dialog_uses_dynamic_sites():
    """The dialog that was reported broken directly - its hardcoded
    ["Primary", "DR"] was spread across multiple lines with a trailing
    comma, a formatting variant the original single-line grep for the
    other 7 dialogs didn't catch."""
    dialog = ServerDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_server_dialog_falls_back_to_primary_dr_when_omitted():
    dialog = ServerDialog()
    assert _items(dialog.site_combo) == ["Primary", "DR"]


def test_storage_dialog_uses_dynamic_sites():
    dialog = StorageDialog(servers=[], sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_storage_dialog_falls_back_to_primary_dr_when_omitted():
    dialog = StorageDialog(servers=[])
    assert _items(dialog.site_combo) == ["Primary", "DR"]


def test_switch_dialog_uses_dynamic_sites():
    dialog = SwitchDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_vlan_dialog_uses_dynamic_sites():
    dialog = VlanDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_backup_destination_dialog_uses_dynamic_sites():
    dialog = BackupDestinationDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_vm_dialog_uses_dynamic_sites():
    dialog = VMDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_rvtools_import_dialog_uses_dynamic_sites():
    dialog = RVToolsImportDialog(sites=THREE_SITES)
    assert _items(dialog.site_combo) == THREE_SITES


def test_import_wizard_dialog_uses_dynamic_sites(tmp_path):
    from pathlib import Path
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("name\n", encoding="utf-8")
    dialog = ImportWizardDialog(Path(csv_path), sites=THREE_SITES)
    assert _items(dialog.default_site_combo) == THREE_SITES
