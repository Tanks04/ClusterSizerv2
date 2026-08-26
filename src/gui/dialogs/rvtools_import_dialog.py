from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.persistence import rvtools_import
from src.gui.error_handling import report_error


class RVToolsImportDialog(QDialog):
    """Import a standard RVTools export (.xlsx, "Export all to Excel" -
    the vHost, vInfo, and vSwitch sheets specifically) into Servers,
    VMs, and (optionally) Switches at once.

    RVTools has no Primary/DR concept of its own, but its "Datacenter"
    column sometimes does distinguish sites in a real multi-site
    environment (Primary and DR living in the same vCenter as two
    Datacenter objects). If the file has just one Datacenter value,
    everything goes to the single site chosen below - same as before.
    If it has more than one, a mapping section appears letting each
    found Datacenter be routed to Primary or DR individually."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from RVTools")
        self.resize(520, 420)

        self._path: str | None = None
        self._servers: list = []
        self._vms: list = []
        self._switches: list = []
        self._dc_combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Reads a standard RVTools export (File \u2192 Export all to Excel in "
            "RVTools) - the vHost sheet becomes Servers, vInfo becomes VMs."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()

        file_row = QWidget()
        file_row_layout = QVBoxLayout(file_row)
        file_row_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No file selected")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse)
        file_row_layout.addWidget(self.path_edit)
        file_row_layout.addWidget(browse_button)
        form.addRow("RVTools file (.xlsx)", file_row)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["Primary", "DR"])
        self.site_combo.setToolTip(
            "Used for everything when only one Datacenter is found in the "
            "file, or as the fallback for any Datacenter value not covered "
            "by the mapping below."
        )
        form.addRow("Default site", self.site_combo)

        self.os_preference_combo = QComboBox()
        self.os_preference_combo.addItems([
            "OS according to the configuration file (declared, always present)",
            "OS according to VMware Tools (detected live, needs Tools installed)",
        ])
        self.os_preference_combo.setToolTip(
            "Which OS source to prefer per VM - falls back to the other "
            "one automatically if the preferred source is blank for that VM."
        )
        form.addRow("OS source", self.os_preference_combo)

        self.import_switches_check = QCheckBox("Also import Switches (name only)")
        self.import_switches_check.setToolTip(
            "Creates a Network Switch entry for each distinct switch name "
            "found - name only; port counts/speed aren't in RVTools' data "
            "in a form this app can use directly, so review those manually."
        )
        form.addRow("", self.import_switches_check)

        layout.addLayout(form)

        self.dc_mapping_box = QGroupBox("Datacenter \u2192 Site mapping (found more than one)")
        self.dc_mapping_layout = QFormLayout(self.dc_mapping_box)
        self.dc_mapping_box.setVisible(False)
        layout.addWidget(self.dc_mapping_box)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #757575; font-style: italic;")
        layout.addWidget(self.preview_label)

        layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.button_box)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select RVTools Export", "", "Excel Workbook (*.xlsx)"
        )
        if not path:
            return

        try:
            vm_count, host_count = rvtools_import.preview_counts(path)
            datacenters = rvtools_import.detect_datacenters(path)
        except rvtools_import.RVToolsImportError as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        except Exception as exc:
            report_error(self, "Import Error", exc)
            return

        self._path = path
        self.path_edit.setText(Path(path).name)

        preview_text = f"Found {vm_count} VM(s) and {host_count} host(s)."
        if len(datacenters) > 1:
            preview_text += f" {len(datacenters)} distinct Datacenters found - map them below."
        self.preview_label.setText(preview_text)

        self._rebuild_dc_mapping(datacenters)

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            vm_count > 0 or host_count > 0
        )

    def _rebuild_dc_mapping(self, datacenters: list[str]) -> None:
        while self.dc_mapping_layout.rowCount():
            self.dc_mapping_layout.removeRow(0)
        self._dc_combos.clear()

        if len(datacenters) < 2:
            self.dc_mapping_box.setVisible(False)
            return

        for dc in datacenters:
            combo = QComboBox()
            combo.addItems(["Primary", "DR"])
            self.dc_mapping_layout.addRow(dc, combo)
            self._dc_combos[dc] = combo

        self.dc_mapping_box.setVisible(True)

    def _on_accept(self):
        site = self.site_combo.currentText()
        site_map = {dc: combo.currentText() for dc, combo in self._dc_combos.items()} or None
        os_preference = "tools" if self.os_preference_combo.currentIndex() == 1 else "config"

        try:
            self._servers = rvtools_import.import_servers(self._path, site=site, site_map=site_map)
            self._vms = rvtools_import.import_vms(
                self._path, site=site, site_map=site_map, os_preference=os_preference,
            )
            self._switches = (
                rvtools_import.import_switches(self._path, site=site, site_map=site_map)
                if self.import_switches_check.isChecked() else []
            )
        except Exception as exc:
            report_error(self, "Import Error", exc)
            return

        self.accept()

    def get_servers(self) -> list:
        return self._servers

    def get_vms(self) -> list:
        return self._vms

    def get_switches(self) -> list:
        return self._switches
