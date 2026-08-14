from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
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
    the vHost and vInfo sheets specifically) into Servers + VMs at once.
    RVTools has no Primary/DR concept of its own - a single export is
    normally one vCenter's inventory - so the whole file is assigned to
    ONE site, chosen here, same as the general Import Wizard's
    target-site pattern."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from RVTools")
        self.resize(480, 220)

        self._path: str | None = None
        self._servers: list = []
        self._vms: list = []

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Reads a standard RVTools export (File \u2192 Export all to Excel in "
            "RVTools) - the vHost sheet becomes Servers, vInfo becomes VMs. "
            "Both are added to the site you choose below."
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
        form.addRow("Import into site", self.site_combo)

        layout.addLayout(form)

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
        except rvtools_import.RVToolsImportError as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        except Exception as exc:
            report_error(self, "Import Error", exc)
            return

        self._path = path
        self.path_edit.setText(Path(path).name)
        self.preview_label.setText(f"Found {vm_count} VM(s) and {host_count} host(s).")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            vm_count > 0 or host_count > 0
        )

    def _on_accept(self):
        site = self.site_combo.currentText()
        try:
            self._servers = rvtools_import.import_servers(self._path)
            self._vms = rvtools_import.import_vms(self._path)
        except Exception as exc:
            report_error(self, "Import Error", exc)
            return

        for server in self._servers:
            server.site = site
        for vm in self._vms:
            vm.site = site

        self.accept()

    def get_servers(self) -> list:
        return self._servers

    def get_vms(self) -> list:
        return self._vms
