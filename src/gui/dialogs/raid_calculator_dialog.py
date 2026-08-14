from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from src.calculations.raid_calculator import (
    compute_raid, RaidConfigError, RAID_LEVELS, DISK_TYPES,
)
from src.services.project_service import ProjectService


class RaidCalculatorDialog(QDialog):
    """Play with RAID sizing without committing to anything - pick a
    target (a Server or Storage already in the project, or none at all)
    and Apply pushes the result there. Changing the target dropdown never
    discards the RAID numbers you've entered; only Apply writes anything
    to the project, and only after confirming if it would overwrite
    existing values."""

    def __init__(self, service: ProjectService, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("RAID Calculator")
        self.resize(480, 480)

        layout = QVBoxLayout(self)

        # --- Inputs ---
        input_box = QGroupBox("Disks")
        form = QFormLayout(input_box)

        self.disk_type_combo = QComboBox()
        self.disk_type_combo.addItems(DISK_TYPES)
        self.disk_type_combo.currentTextChanged.connect(self._recompute)
        form.addRow("Disk type", self.disk_type_combo)

        self.disk_size_spin = QSpinBox()
        self.disk_size_spin.setRange(1, 1000)
        self.disk_size_spin.setValue(4)
        self.disk_size_spin.setSuffix(" TB")
        self.disk_size_spin.valueChanged.connect(self._recompute)
        form.addRow("Disk size", self.disk_size_spin)

        self.disk_count_spin = QSpinBox()
        self.disk_count_spin.setRange(1, 256)
        self.disk_count_spin.setValue(8)
        self.disk_count_spin.valueChanged.connect(self._recompute)
        form.addRow("Number of disks", self.disk_count_spin)

        self.raid_level_combo = QComboBox()
        self.raid_level_combo.addItems(RAID_LEVELS)
        self.raid_level_combo.setCurrentText("RAID 5")
        self.raid_level_combo.currentTextChanged.connect(self._on_raid_level_changed)
        form.addRow("RAID level", self.raid_level_combo)

        self.hot_spares_spin = QSpinBox()
        self.hot_spares_spin.setRange(0, 32)
        self.hot_spares_spin.valueChanged.connect(self._recompute)
        form.addRow("Hot spares", self.hot_spares_spin)

        self.groups_spin = QSpinBox()
        self.groups_spin.setRange(2, 16)
        self.groups_spin.setValue(2)
        self.groups_spin.valueChanged.connect(self._recompute)
        self.groups_label = QLabel("Groups (RAID 50/60)")
        form.addRow(self.groups_label, self.groups_spin)

        layout.addWidget(input_box)

        # --- Output ---
        output_box = QGroupBox("Result")
        output_layout = QVBoxLayout(output_box)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        output_layout.addWidget(self.result_label)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #ed6c02; font-weight: bold;")
        output_layout.addWidget(self.warning_label)

        layout.addWidget(output_box)

        # --- Target ---
        target_box = QGroupBox("Apply to")
        target_form = QFormLayout(target_box)

        self.target_type_combo = QComboBox()
        self.target_type_combo.addItems(["None (just calculating)", "Server", "Storage"])
        self.target_type_combo.currentTextChanged.connect(self._on_target_type_changed)
        target_form.addRow("Target", self.target_type_combo)

        self.target_entity_combo = QComboBox()
        self.target_entity_combo.setEnabled(False)
        target_form.addRow("Which one", self.target_entity_combo)

        layout.addWidget(target_box)

        button_row = QHBoxLayout()
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset)
        button_row.addWidget(reset_button)

        button_row.addStretch()

        self.apply_button = QPushButton("Apply")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        button_row.addWidget(self.apply_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)

        self._current_result = None
        self._on_raid_level_changed(self.raid_level_combo.currentText())
        self._recompute()

    def _on_raid_level_changed(self, level: str):
        is_nested = level in ("RAID 50", "RAID 60")
        self.groups_spin.setVisible(is_nested)
        self.groups_label.setVisible(is_nested)
        self._recompute()

    def _recompute(self):
        try:
            result = compute_raid(
                disk_size=self.disk_size_spin.value(),
                disk_count=self.disk_count_spin.value(),
                raid_level=self.raid_level_combo.currentText(),
                hot_spares=self.hot_spares_spin.value(),
                groups=self.groups_spin.value(),
                disk_type=self.disk_type_combo.currentText(),
            )
        except RaidConfigError as exc:
            self._current_result = None
            self.result_label.setText(f"\u26a0 {exc}")
            self.warning_label.setText("")
            self._update_apply_enabled()
            return

        self._current_result = result
        self.result_label.setText(
            f"<b>Raw:</b> {result.raw_capacity:.1f} TB &nbsp;\u00b7&nbsp; "
            f"<b>Usable:</b> {result.usable_capacity:.1f} TB &nbsp;\u00b7&nbsp; "
            f"<b>Overhead:</b> {result.overhead_percent:.1f}%<br>"
            f"<b>Effective disks:</b> {result.effective_disk_count}<br>"
            f"{result.fault_tolerance}"
        )
        self.warning_label.setText(f"\u26a0 {result.warning}" if result.warning else "")
        self._update_apply_enabled()

    def _on_target_type_changed(self, target_type: str):
        self.target_entity_combo.clear()

        if target_type == "Server":
            self.target_entity_combo.setEnabled(True)
            for i, server in enumerate(self.service.project.servers):
                self.target_entity_combo.addItem(f"{server.name} ({server.site})", i)
        elif target_type == "Storage":
            self.target_entity_combo.setEnabled(True)
            for i, storage in enumerate(self.service.project.storages):
                self.target_entity_combo.addItem(f"{storage.name} ({storage.site})", i)
        else:
            self.target_entity_combo.setEnabled(False)

        self._update_apply_enabled()

    def _update_apply_enabled(self):
        target_type = self.target_type_combo.currentText()
        has_target = target_type != "None (just calculating)" and self.target_entity_combo.count() > 0
        self.apply_button.setEnabled(self._current_result is not None and has_target)

    def _reset(self):
        self.disk_type_combo.setCurrentIndex(0)
        self.disk_size_spin.setValue(4)
        self.disk_count_spin.setValue(8)
        self.raid_level_combo.setCurrentText("RAID 5")
        self.hot_spares_spin.setValue(0)
        self.groups_spin.setValue(2)
        self._recompute()

    def _apply(self):
        if self._current_result is None:
            return

        target_type = self.target_type_combo.currentText()
        index = self.target_entity_combo.currentData()
        if index is None:
            return

        if target_type == "Storage":
            self._apply_to_storage(index)
        elif target_type == "Server":
            self._apply_to_server(index)

    def _apply_to_storage(self, index: int):
        storage = self.service.project.storages[index]
        result = self._current_result

        has_existing = storage.raw_capacity_tb > 0 or storage.usable_capacity_tb > 0
        if has_existing:
            reply = QMessageBox.question(
                self, "Apply RAID Calculation",
                f"{storage.name} already has capacity set "
                f"({storage.raw_capacity_tb:.1f} TB raw / "
                f"{storage.usable_capacity_tb:.1f} TB usable). "
                "Overwrite with the calculated values?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        storage.raw_capacity_tb = round(result.raw_capacity, 2)
        storage.usable_capacity_tb = round(result.usable_capacity, 2)
        storage.raid_overhead_percent = round(result.overhead_percent, 1)
        self.service.update_storage(index, storage)

        QMessageBox.information(self, "Apply RAID Calculation", f"Applied to {storage.name}.")

    def _apply_to_server(self, index: int):
        server = self.service.project.servers[index]
        result = self._current_result

        note = (
            f"Local RAID: {self.disk_count_spin.value()}x {self.disk_size_spin.value()}TB "
            f"{self.disk_type_combo.currentText()} in {self.raid_level_combo.currentText()}"
            + (f" + {self.hot_spares_spin.value()} hot spare(s)" if self.hot_spares_spin.value() else "")
            + f" = {result.usable_capacity:.1f} TB usable, {result.fault_tolerance.lower()}."
        )
        server.notes = f"{server.notes}\n{note}".strip() if server.notes else note
        self.service.update_server(index, server)

        QMessageBox.information(self, "Apply RAID Calculation", f"Added to {server.name}'s notes.")
