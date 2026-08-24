from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.import_profile import (
    ImportProfile, ColumnMapping, VM_TARGET_FIELDS, REQUIRED_VM_FIELDS, SIZE_UNITS,
)
from src.persistence import generic_import, import_presets, import_profile_store
from src.persistence.import_engine import best_matching_profile, convert_rows
from src.gui.error_handling import report_error

FIELD_LABELS = {
    "name": "Name *",
    "site": "Site (optional - falls back to the default below)",
    "vcpu": "vCPU *",
    "ram_gb": "RAM *",
    "disk_gb": "Disk *",
    "powered_on": "Power state",
    "ip_address": "IP Address",
    "notes": "Notes",
}

NOT_MAPPED = "-- not mapped --"
CURRENT_SHEET = "(current sheet)"


class ImportWizardDialog(QDialog):
    """Import any CSV/XLSX/JSON VM export by mapping its columns to
    ClusterSizer fields - once, then save the mapping as a reusable
    profile so the next export from the same tool needs zero re-mapping.

    For multi-sheet XLSX (e.g. RVTools' vInfo/vCPU/vPartition/...), each
    FIELD can independently pull from a different sheet than the primary
    one - joined by whatever the Name field's own column is (e.g.
    RVTools' "VM" column, consistent across its sheets). Pick a sheet per
    field one at a time until every field you need is mapped."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(f"Import Wizard - {self.path.name}")
        self.resize(760, 700)

        self._raw_rows: list[list] = []
        self._header: list[str] = []
        self._data_rows: list[dict] = []
        self._field_combos: dict[str, QComboBox] = {}
        self._unit_combos: dict[str, QComboBox] = {}
        self._field_sheet_combos: dict[str, QComboBox] = {}

        # Lazy cache for OTHER sheets referenced by a per-field sheet
        # choice - keyed by sheet name, populated on first use so we
        # don't eagerly read all 27 sheets of a large workbook up front.
        self._sheet_header_cache: dict[str, list[str]] = {}
        self._sheet_rows_cache: dict[str, list[dict]] = {}

        self._build_ui()
        self._load_file()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.sheet_combo = QComboBox()
        self.sheet_combo.setVisible(False)
        self.sheet_combo.currentIndexChanged.connect(self._load_file)
        top_row.addWidget(QLabel("Sheet:"))
        top_row.addWidget(self.sheet_combo)
        top_row.addStretch()
        layout.addLayout(top_row)

        header_row_form = QFormLayout()
        self.header_row_spin = QSpinBox()
        self.header_row_spin.setRange(1, 50)
        self.header_row_spin.setValue(1)
        self.header_row_spin.valueChanged.connect(self._on_header_row_changed)
        header_row_form.addRow("Header is on row", self.header_row_spin)
        layout.addLayout(header_row_form)

        layout.addWidget(QLabel("Raw preview (adjust the header row above until it lines up):"))
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(160)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_row.addWidget(self.profile_combo, stretch=1)
        layout.addLayout(profile_row)

        self.mapping_box = QGroupBox("Column mapping")
        self.mapping_form = QFormLayout(self.mapping_box)
        layout.addWidget(self.mapping_box)

        extra_form = QFormLayout()

        self.default_site_combo = QComboBox()
        self.default_site_combo.addItems(["Primary", "DR"])
        extra_form.addRow("Default site", self.default_site_combo)

        self.powered_on_edit = QLineEdit("Powered On")
        self.powered_on_edit.setToolTip(
            "Exact text in the mapped power-state column that means 'on' "
            "(e.g. 'Powered On', 'running', 'poweredOn')."
        )
        extra_form.addRow("\"Powered on\" text is", self.powered_on_edit)

        self.skip_prefixes_edit = QLineEdit()
        self.skip_prefixes_edit.setPlaceholderText("e.g. vCLS-, template-  (comma separated, optional)")
        extra_form.addRow("Skip names starting with", self.skip_prefixes_edit)

        layout.addLayout(extra_form)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.result_label)

        save_row = QHBoxLayout()
        self.save_profile_check = QCheckBox("Save this mapping as a profile named:")
        self.save_profile_name_edit = QLineEdit()
        save_row.addWidget(self.save_profile_check)
        save_row.addWidget(self.save_profile_name_edit, stretch=1)
        layout.addLayout(save_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._all_profiles = import_presets.PRESETS + import_profile_store.load_user_profiles()
        self.profile_combo.addItem("(manual mapping)", None)
        for p in self._all_profiles:
            self.profile_combo.addItem(p.name, p)

    # ------------------------------------------------------------------
    # File / sheet / header-row handling
    # ------------------------------------------------------------------

    def _load_file(self):
        self._sheet_header_cache.clear()
        self._sheet_rows_cache.clear()

        if not self.sheet_combo.isVisible():
            try:
                sheets = generic_import.sheet_names(self.path)
            except generic_import.UnsupportedFileError as exc:
                report_error(self, "Import Error", exc)
                self.reject()
                return
            if len(sheets) > 1:
                # Populate the dropdown WITHOUT relying on addItems() to
                # reliably fire currentIndexChanged and re-trigger this
                # method on its own - that's fragile (observed: the first
                # sheet sometimes never actually loads). Block the signal
                # and fall through to load the first sheet directly instead.
                self.sheet_combo.blockSignals(True)
                self.sheet_combo.setVisible(True)
                self.sheet_combo.addItems(sheets)
                self.sheet_combo.blockSignals(False)

        sheet = self.sheet_combo.currentText() if self.sheet_combo.isVisible() else None

        try:
            self._raw_rows = generic_import.load_raw_rows(self.path, sheet=sheet)
        except generic_import.UnsupportedFileError as exc:
            QMessageBox.critical(self, "Import Error", f"Couldn't read the file:\n{exc}")
            self.reject()
            return
        except Exception as exc:
            report_error(self, "Import Error", exc)
            self.reject()
            return

        if not self._raw_rows:
            QMessageBox.warning(self, "Import", "The file appears to be empty.")
            self.reject()
            return

        guess = generic_import.guess_header_row(self._raw_rows)
        self.header_row_spin.setMaximum(max(1, len(self._raw_rows)))
        self.header_row_spin.blockSignals(True)
        self.header_row_spin.setValue(guess + 1)
        self.header_row_spin.blockSignals(False)

        self._refresh_preview_table()
        self._apply_header_row()

        matched = best_matching_profile(self._header, self._all_profiles)
        if matched:
            idx = self.profile_combo.findText(matched.name)
            if idx >= 0:
                # setCurrentIndex() emits currentIndexChanged only when the
                # index actually changes - a NO-OP here (e.g. this sheet and
                # the previous one both best-match the same profile) would
                # silently skip rebuilding the mapping UI, leaving it showing
                # the PREVIOUS sheet's columns. Call it directly instead of
                # relying on the signal.
                self.profile_combo.blockSignals(True)
                self.profile_combo.setCurrentIndex(idx)
                self.profile_combo.blockSignals(False)
                self._on_profile_selected()
                return

        self._rebuild_mapping_ui(None)

    def _refresh_preview_table(self):
        preview_rows = self._raw_rows[:8]
        max_cols = max((len(r) for r in preview_rows), default=0)
        self.preview_table.setRowCount(len(preview_rows))
        self.preview_table.setColumnCount(max_cols)
        for r, row in enumerate(preview_rows):
            for c in range(max_cols):
                value = row[c] if c < len(row) else ""
                self.preview_table.setItem(r, c, QTableWidgetItem(str(value)))

    def _on_header_row_changed(self):
        self._sheet_header_cache.clear()
        self._sheet_rows_cache.clear()
        self._apply_header_row()
        # Re-check whether the currently chosen mapping's columns still exist
        self._rebuild_mapping_ui(self._current_profile())

    def _apply_header_row(self):
        header_index = self.header_row_spin.value() - 1
        try:
            self._header, self._data_rows = generic_import.rows_to_dicts(self._raw_rows, header_index)
        except IndexError:
            self._header, self._data_rows = [], []

    def _available_sheets(self) -> list[str]:
        """All sheet names in the workbook, for the per-field sheet
        combos - empty for single-sheet files (CSV/JSON, or an XLSX with
        only one sheet), in which case those combos just won't be shown."""
        if not self.sheet_combo.isVisible():
            return []
        return [self.sheet_combo.itemText(i) for i in range(self.sheet_combo.count())]

    def _get_sheet_data(self, sheet_name: str) -> tuple[list[str], list[dict]]:
        """Loads and caches ONE other sheet's (header, rows), using the
        SAME header-row position as the primary sheet - a reasonable
        assumption for one tool's own multi-sheet export, and the wizard
        still lets you fix the primary header row if that's ever wrong."""
        if sheet_name not in self._sheet_rows_cache:
            try:
                raw = generic_import.load_raw_rows(self.path, sheet=sheet_name)
                header_index = self.header_row_spin.value() - 1
                header, rows = generic_import.rows_to_dicts(raw, header_index)
            except Exception:
                header, rows = [], []
            self._sheet_header_cache[sheet_name] = header
            self._sheet_rows_cache[sheet_name] = rows
        return self._sheet_header_cache[sheet_name], self._sheet_rows_cache[sheet_name]

    def _gather_sheets_data(self) -> dict[str, list[dict]]:
        """Collects (name -> rows) for every OTHER sheet actually
        referenced by a field's sheet combo right now - only those, not
        the whole workbook, so a 27-sheet file doesn't get fully read
        just because a couple of fields use non-primary sheets."""
        sheets_data = {}
        for combo in self._field_sheet_combos.values():
            sheet_name = combo.currentText()
            if sheet_name and sheet_name != CURRENT_SHEET and sheet_name not in sheets_data:
                _, rows = self._get_sheet_data(sheet_name)
                sheets_data[sheet_name] = rows
        return sheets_data

    # ------------------------------------------------------------------
    # Profile / mapping UI
    # ------------------------------------------------------------------

    def _current_profile(self) -> ImportProfile | None:
        return self.profile_combo.currentData()

    def _on_profile_selected(self):
        profile = self._current_profile()
        self._rebuild_mapping_ui(profile)
        if profile:
            if profile.powered_on_value:
                self.powered_on_edit.setText(profile.powered_on_value)
            self.skip_prefixes_edit.setText(", ".join(profile.skip_name_prefixes))

    def _rebuild_mapping_ui(self, profile: ImportProfile | None):
        while self.mapping_form.rowCount():
            self.mapping_form.removeRow(0)
        self._field_combos.clear()
        self._unit_combos.clear()
        self._field_sheet_combos.clear()

        available_sheets = self._available_sheets()

        for field in VM_TARGET_FIELDS:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            existing = profile.mapping_for(field) if profile else None
            existing_sheet = (existing.source_sheet if existing else "") or CURRENT_SHEET

            combo = QComboBox()
            self._field_combos[field] = combo

            if len(available_sheets) > 1:
                sheet_combo = QComboBox()
                sheet_combo.addItem(CURRENT_SHEET)
                sheet_combo.addItems(available_sheets)
                if existing_sheet in available_sheets or existing_sheet == CURRENT_SHEET:
                    sheet_combo.setCurrentText(existing_sheet)
                sheet_combo.currentIndexChanged.connect(
                    lambda _idx, f=field: self._on_field_sheet_changed(f)
                )
                sheet_combo.setToolTip(
                    "Pull this field from a DIFFERENT sheet in the same "
                    "workbook, joined by the Name field's own column "
                    "(e.g. RVTools' \"VM\" column, consistent across its sheets)."
                )
                row_layout.addWidget(sheet_combo)
                self._field_sheet_combos[field] = sheet_combo

            self._populate_column_combo(field, combo, existing_sheet, existing)
            combo.currentIndexChanged.connect(self._update_result_preview)

            row_layout.addWidget(combo, stretch=1)

            if field in ("ram_gb", "disk_gb"):
                unit_combo = QComboBox()
                unit_combo.addItems(SIZE_UNITS)
                if existing:
                    idx = unit_combo.findText(existing.unit)
                    if idx >= 0:
                        unit_combo.setCurrentIndex(idx)
                unit_combo.currentIndexChanged.connect(self._update_result_preview)
                row_layout.addWidget(unit_combo)
                self._unit_combos[field] = unit_combo

            self.mapping_form.addRow(FIELD_LABELS[field], row_widget)

    def _populate_column_combo(self, field: str, combo: QComboBox, sheet_name: str, existing: ColumnMapping | None):
        """Fills a field's column combo with whichever sheet's columns
        are relevant - the primary sheet's self._header, or another
        sheet's header if that field's own sheet combo points elsewhere."""
        if sheet_name == CURRENT_SHEET:
            header = self._header
        else:
            header, _ = self._get_sheet_data(sheet_name)

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(NOT_MAPPED)
        combo.addItems(header)
        if existing and existing.source_column in header:
            combo.setCurrentText(existing.source_column)
        combo.blockSignals(False)

    def _on_field_sheet_changed(self, field: str):
        sheet_combo = self._field_sheet_combos.get(field)
        combo = self._field_combos.get(field)
        if sheet_combo is None or combo is None:
            return
        self._populate_column_combo(field, combo, sheet_combo.currentText(), None)
        self._update_result_preview()

        self._update_result_preview()

    def _build_profile_from_ui(self, name: str = "") -> ImportProfile:
        mappings = []
        for field, combo in self._field_combos.items():
            source = combo.currentText()
            if source == NOT_MAPPED:
                source = ""
            unit = self._unit_combos[field].currentText() if field in self._unit_combos else "auto"
            sheet_combo = self._field_sheet_combos.get(field)
            source_sheet = ""
            if sheet_combo is not None and sheet_combo.currentText() != CURRENT_SHEET:
                source_sheet = sheet_combo.currentText()
            mappings.append(ColumnMapping(
                target_field=field, source_column=source, unit=unit, source_sheet=source_sheet,
            ))

        prefixes = [p.strip() for p in self.skip_prefixes_edit.text().split(",") if p.strip()]

        return ImportProfile(
            name=name or self.save_profile_name_edit.text().strip() or "Untitled",
            header_row=self.header_row_spin.value(),
            mappings=mappings,
            powered_on_value=self.powered_on_edit.text() or "Powered On",
            skip_name_prefixes=prefixes,
            built_in=False,
        )

    # ------------------------------------------------------------------
    # Live result preview + final import
    # ------------------------------------------------------------------

    # Live preview re-converts on every combo box change, so it's capped
    # to a sample - the real import (on accept) always recomputes over
    # the full file, independently of this. Only the LIVE COUNT shown
    # while adjusting mappings is an estimate on large files.
    _PREVIEW_SAMPLE_SIZE = 200

    def _update_result_preview(self):
        profile = self._build_profile_from_ui()
        if not profile.is_complete():
            missing = [f for f in REQUIRED_VM_FIELDS if not (profile.mapping_for(f) and profile.mapping_for(f).source_column)]
            self.result_label.setText(f"Map all required fields first (missing: {', '.join(missing)}).")
            self.imported_vms = []
            return

        total_rows = len(self._data_rows)
        sample = self._data_rows[: self._PREVIEW_SAMPLE_SIZE]
        sheets_data = self._gather_sheets_data()
        vms, skipped = convert_rows(sample, profile, site=self.default_site_combo.currentText(), sheets_data=sheets_data)
        self.imported_vms = vms  # overwritten with the full-file result in _on_accept()

        if total_rows > self._PREVIEW_SAMPLE_SIZE:
            text = (
                f"Preview (first {self._PREVIEW_SAMPLE_SIZE} of {total_rows} rows): "
                f"{len(vms)} ready"
            )
            if skipped:
                text += f", {skipped} skipped"
            text += ". The full file is processed when you click OK."
        else:
            text = f"Ready to import {len(vms)} VM(s)."
            if skipped:
                text += f" ({skipped} skipped by name-prefix filter.)"
        self.result_label.setText(text)

    def _on_accept(self):
        profile = self._build_profile_from_ui()
        if not profile.is_complete():
            QMessageBox.warning(self, "Import", "Map all required fields (Name, vCPU, RAM, Disk) before importing.")
            return

        vms, skipped = convert_rows(
            self._data_rows, profile, site=self.default_site_combo.currentText(),
            sheets_data=self._gather_sheets_data(),
        )
        if not vms:
            QMessageBox.warning(self, "Import", "No VMs matched this mapping - nothing to import.")
            return
        self.imported_vms = vms
        self._import_skipped = skipped

        if self.save_profile_check.isChecked():
            name = self.save_profile_name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Import", "Enter a name for the profile, or uncheck 'Save this mapping'.")
                return
            try:
                import_profile_store.add_or_replace_profile(self._build_profile_from_ui(name=name))
            except OSError as exc:
                QMessageBox.warning(
                    self, "Profile Not Saved",
                    f"The mapping profile could not be saved ({exc}), but the "
                    "import will continue - you'll just need to map this "
                    "format again next time.",
                )

        self.accept()

    def get_imported_vms(self):
        return getattr(self, "imported_vms", [])

    def get_skipped_count(self) -> int:
        return getattr(self, "_import_skipped", 0)
