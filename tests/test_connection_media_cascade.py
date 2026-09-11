"""Tests for the cascading Speed -> Connector -> Detail connection
media classification, requested directly after the previous flat
MEDIA_OPTIONS list still allowed physically-impossible combinations
(1G on an SFP+, which is actually a 10G+ form factor). Also covers the
new Cable Length field, the repurposed optional "exact part" text
field, and the shared connection_media_summary() display helper.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from src.calculations.thresholds import Thresholds
from src.models.cluster_project import ClusterProject
from src.models.network_connection import (
    CONNECTOR_TO_DETAILS,
    FC_DETAILS,
    SPEED_TO_CONNECTORS,
    NetworkConnection,
    connection_media_summary,
)
from src.models.network_switch import NetworkSwitch
from src.models.server import Server


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _dialog_with_endpoints():
    from src.gui.dialogs.connection_dialog import ConnectionDialog

    project = ClusterProject()
    srv = Server.create_default()
    sw = NetworkSwitch.create_default()
    project.servers.append(srv)
    project.switches.append(sw)
    dialog = ConnectionDialog(project)
    dialog.combo_a.setCurrentIndex(dialog.combo_a.findData(srv.uid))
    dialog.combo_b.setCurrentIndex(dialog.combo_b.findData(sw.uid))
    return dialog


# ----------------------------------------------------------------------
# The cascade mapping itself
# ----------------------------------------------------------------------

def test_1g_does_not_offer_sfp_plus():
    """The exact physical impossibility reported - SFP+ is a 10G+ form
    factor, not 1G's partner (plain SFP is)."""
    assert "SFP+" not in SPEED_TO_CONNECTORS["1G"]
    assert "SFP" in SPEED_TO_CONNECTORS["1G"]


def test_10g_offers_sfp_plus_not_plain_sfp():
    assert "SFP+" in SPEED_TO_CONNECTORS["10G"]
    assert "SFP" not in SPEED_TO_CONNECTORS["10G"]


def test_fc_and_sas_have_no_connector_options():
    assert SPEED_TO_CONNECTORS["FC"] == []
    assert SPEED_TO_CONNECTORS["SAS"] == []


def test_sfp_plus_details_cover_fiber_and_factory_cables():
    details = CONNECTOR_TO_DETAILS["SFP+"]
    assert any("SR" in d for d in details)
    assert any("LR" in d for d in details)
    assert "DAC" in details
    assert "AOC" in details


def test_fc_details_are_shortwave_and_longwave():
    assert any("SW" in d and "Shortwave" in d for d in FC_DETAILS)
    assert any("LW" in d and "Longwave" in d for d in FC_DETAILS)


# ----------------------------------------------------------------------
# ConnectionDialog cascade UI
# ----------------------------------------------------------------------

def test_1g_connector_options_exclude_sfp_plus():
    dialog = _dialog_with_endpoints()

    dialog.speed_combo.setCurrentText("1G")

    items = [dialog.connector_combo.itemText(i) for i in range(dialog.connector_combo.count())]
    assert items == ["RJ45", "SFP"]


def test_selecting_sfp_shows_copper_and_fiber_details():
    dialog = _dialog_with_endpoints()
    dialog.speed_combo.setCurrentText("1G")

    dialog.connector_combo.setCurrentText("SFP")

    items = [dialog.detail_combo.itemText(i) for i in range(dialog.detail_combo.count())]
    assert items == ["Copper", "Fiber"]


def test_fc_hides_connector_and_populates_detail_directly():
    dialog = _dialog_with_endpoints()

    dialog.speed_combo.setCurrentText("FC")

    assert dialog.form_layout.isRowVisible(dialog.connector_combo) is False
    assert dialog.form_layout.isRowVisible(dialog.detail_combo) is True
    items = [dialog.detail_combo.itemText(i) for i in range(dialog.detail_combo.count())]
    assert items == FC_DETAILS


def test_sas_hides_both_connector_and_detail():
    dialog = _dialog_with_endpoints()

    dialog.speed_combo.setCurrentText("SAS")

    assert dialog.form_layout.isRowVisible(dialog.connector_combo) is False
    assert dialog.form_layout.isRowVisible(dialog.detail_combo) is False


def test_full_cascade_saves_correctly():
    dialog = _dialog_with_endpoints()
    dialog.speed_combo.setCurrentText("1G")
    dialog.connector_combo.setCurrentText("SFP")
    dialog.detail_combo.setCurrentText("Fiber")
    dialog.cable_length_edit.setText("3m")
    dialog.media_edit.setText("GLC-SX-MMD")

    connection = dialog.get_connection()

    assert connection.speed == "1G"
    assert connection.connector == "SFP"
    assert connection.media_detail == "Fiber"
    assert connection.cable_length == "3m"
    assert connection.media == "GLC-SX-MMD"


def test_fc_saves_empty_connector_but_real_detail():
    dialog = _dialog_with_endpoints()
    dialog.speed_combo.setCurrentText("FC")
    dialog.detail_combo.setCurrentText("SW (Shortwave/Multimode)")

    connection = dialog.get_connection()

    assert connection.connector == ""
    assert connection.media_detail == "SW (Shortwave/Multimode)"


def test_sas_saves_empty_connector_and_detail():
    dialog = _dialog_with_endpoints()
    dialog.speed_combo.setCurrentText("SAS")

    connection = dialog.get_connection()

    assert connection.connector == ""
    assert connection.media_detail == ""


def test_editing_an_existing_connection_preloads_the_full_cascade():
    from src.gui.dialogs.connection_dialog import ConnectionDialog

    project = ClusterProject()
    existing = NetworkConnection.create_default()
    existing.speed = "10G"
    existing.connector = "SFP+"
    existing.media_detail = "DAC"
    existing.cable_length = "2m"
    existing.media = "FS-10G-DAC-2M"

    dialog = ConnectionDialog(project, existing)

    assert dialog.speed_combo.currentText() == "10G"
    assert dialog.connector_combo.currentText() == "SFP+"
    assert dialog.detail_combo.currentText() == "DAC"
    assert dialog.cable_length_edit.text() == "2m"
    assert dialog.media_edit.text() == "FS-10G-DAC-2M"


def test_switching_speed_after_editing_refreshes_the_cascade():
    from src.gui.dialogs.connection_dialog import ConnectionDialog

    project = ClusterProject()
    existing = NetworkConnection.create_default()
    existing.speed = "10G"
    existing.connector = "SFP+"
    existing.media_detail = "DAC"
    dialog = ConnectionDialog(project, existing)

    dialog.speed_combo.setCurrentText("1G")

    items = [dialog.connector_combo.itemText(i) for i in range(dialog.connector_combo.count())]
    assert items == ["RJ45", "SFP"]
    assert "SFP+" not in items


# ----------------------------------------------------------------------
# Backward compatibility with pre-cascade saved connections
# ----------------------------------------------------------------------

def test_old_generic_media_value_preserved_as_exact_part():
    from src.gui.dialogs.connection_dialog import ConnectionDialog

    project = ClusterProject()
    old_conn = NetworkConnection.create_default()
    old_conn.connector = ""
    old_conn.media_detail = ""
    old_conn.speed = "FC"
    old_conn.media = "FC"

    dialog = ConnectionDialog(project, old_conn)

    assert dialog.media_edit.text() == "FC"


def test_cascade_fields_clsz_round_trip(tmp_path):
    from src.persistence import project_repository

    project = ClusterProject(name="Cascade round trip")
    conn = NetworkConnection.create_default()
    conn.connector = "SFP+"
    conn.media_detail = "DAC"
    conn.cable_length = "3m"
    conn.media = "FS-QSFP-DAC-3M"
    project.connections.append(conn)
    path = tmp_path / "p.clsz"

    project_repository.save_project(project, path, Thresholds())
    loaded = project_repository.load_project(path)

    lc = loaded.project.connections[0]
    assert lc.connector == "SFP+"
    assert lc.media_detail == "DAC"
    assert lc.cable_length == "3m"
    assert lc.media == "FS-QSFP-DAC-3M"


def test_old_clsz_file_without_cascade_fields_defaults_gracefully(tmp_path):
    import json

    from src.persistence import project_repository

    project = ClusterProject(name="Pre-cascade")
    conn = NetworkConnection.create_default()
    conn.media = "FC"
    project.connections.append(conn)
    path = tmp_path / "old.clsz"
    project_repository.save_project(project, path, Thresholds())

    raw = json.loads(path.read_text(encoding="utf-8"))
    for field in ("connector", "media_detail", "cable_length"):
        del raw["connections"][0][field]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = project_repository.load_project(path)

    lc = loaded.project.connections[0]
    assert lc.connector == ""
    assert lc.media_detail == ""
    assert lc.cable_length == ""
    assert lc.media == "FC"


# ----------------------------------------------------------------------
# connection_media_summary() - shared display helper
# ----------------------------------------------------------------------

def test_summary_combines_classification_and_exact_part():
    conn = NetworkConnection.create_default()
    conn.connector = "SFP+"
    conn.media_detail = "DAC"
    conn.media = "FS-10G-DAC-2M"

    assert connection_media_summary(conn) == "SFP+ DAC (FS-10G-DAC-2M)"


def test_summary_classification_only():
    conn = NetworkConnection.create_default()
    conn.connector = "FC"
    conn.media_detail = "SW (Shortwave/Multimode)"

    assert connection_media_summary(conn) == "FC SW (Shortwave/Multimode)"


def test_summary_legacy_value_only():
    conn = NetworkConnection.create_default()
    conn.connector = ""
    conn.media_detail = ""
    conn.media = "FC"

    assert connection_media_summary(conn) == "FC"


def test_summary_nothing_set():
    conn = NetworkConnection.create_default()
    conn.connector = ""
    conn.media_detail = ""

    assert connection_media_summary(conn) == "-"


# ----------------------------------------------------------------------
# Connections table - Media summary + new Cable Length column
# ----------------------------------------------------------------------

def test_connections_table_shows_media_summary_and_cable_length():
    from PySide6.QtCore import Qt

    from src.gui.models.connection_table_model import ConnectionTableModel

    conn = NetworkConnection.create_default()
    conn.connector = "SFP+"
    conn.media_detail = "DAC"
    conn.media = "FS-10G-DAC-2M"
    conn.cable_length = "2m"
    model = ConnectionTableModel([conn])

    media_col = model.HEADERS.index("Media")
    length_col = model.HEADERS.index("Cable Length")
    assert model.data(model.index(0, media_col), Qt.ItemDataRole.DisplayRole) == "SFP+ DAC (FS-10G-DAC-2M)"
    assert model.data(model.index(0, length_col), Qt.ItemDataRole.DisplayRole) == "2m"


def test_connections_table_shows_dash_for_no_cable_length():
    from PySide6.QtCore import Qt

    from src.gui.models.connection_table_model import ConnectionTableModel

    conn = NetworkConnection.create_default()
    model = ConnectionTableModel([conn])

    length_col = model.HEADERS.index("Cable Length")
    assert model.data(model.index(0, length_col), Qt.ItemDataRole.DisplayRole) == "-"


# ----------------------------------------------------------------------
# Word report - Media summary + new Cable Length column
# ----------------------------------------------------------------------

def test_docx_report_connections_table_shows_cascade_data():
    from src.calculations.docx_report import build_docx_report

    project = ClusterProject()
    srv = Server.create_default()
    sw = NetworkSwitch.create_default()
    project.servers.append(srv)
    project.switches.append(sw)
    conn = NetworkConnection.create_default()
    conn.server_uid = srv.uid
    conn.switch_uid = sw.uid
    conn.speed = "10G"
    conn.connector = "SFP+"
    conn.media_detail = "DAC"
    conn.cable_length = "2m"
    project.connections.append(conn)

    doc = build_docx_report(project, Thresholds(), app_version="test")

    table = next(t for t in doc.tables if "Cable Length" in [c.text for c in t.rows[0].cells])
    headers = [c.text for c in table.rows[0].cells]
    row = [c.text for c in table.rows[1].cells]
    assert row[headers.index("Media")] == "SFP+ DAC"
    assert row[headers.index("Cable Length")] == "2m"
