"""Generic multi-select bulk-edit dialog - one checkbox+input row per
field, only CHECKED fields get applied to every selected row. Used by
Servers/Storage/VMs' right-click "Bulk Edit Selected" action so a
mis-entered value (e.g. disk count/size typed wrong on several
identical servers) can be fixed across many rows in one action instead
of editing each row's dialog separately.
"""

from dataclasses import dataclass, field as dataclass_field

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass
class BulkEditField:
    attr: str
    label: str
    kind: str  # "int", "float", "bool", "combo"
    suffix: str = ""
    combo_options: list[str] = dataclass_field(default_factory=list)
    min_value: float = 0
    max_value: float = 1_000_000
    decimals: int = 2


class BulkEditDialog(QDialog):

    def __init__(self, entity_kind: str, count: int, fields: list[BulkEditField], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bulk Edit {count} {entity_kind}(s)")
        self.resize(420, 80 + 40 * len(fields))
        self._fields = fields
        self._checks: dict[str, QCheckBox] = {}
        self._widgets: dict[str, object] = {}

        layout = QVBoxLayout(self)

        info = QLabel(
            f"Check which field(s) to set on all {count} selected {entity_kind}(s) - "
            "unchecked fields are left untouched on every row."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        for spec in fields:
            row = QHBoxLayout()
            check = QCheckBox()
            self._checks[spec.attr] = check
            row.addWidget(check)

            widget = self._make_widget(spec)
            widget.setEnabled(False)
            check.toggled.connect(widget.setEnabled)
            self._widgets[spec.attr] = widget
            row.addWidget(widget)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            form.addRow(spec.label, container)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _make_widget(spec: BulkEditField):
        if spec.kind == "int":
            w = QSpinBox()
            w.setRange(int(spec.min_value), int(spec.max_value))
            if spec.suffix:
                w.setSuffix(spec.suffix)
            return w
        if spec.kind == "float":
            w = QDoubleSpinBox()
            w.setRange(spec.min_value, spec.max_value)
            w.setDecimals(spec.decimals)
            if spec.suffix:
                w.setSuffix(spec.suffix)
            return w
        if spec.kind == "bool":
            return QCheckBox()
        if spec.kind == "combo":
            w = QComboBox()
            w.addItems(spec.combo_options)
            return w
        raise ValueError(f"Unknown BulkEditField kind: {spec.kind}")

    def get_updates(self) -> dict:
        """Only fields whose checkbox is checked - empty dict means
        nothing was selected, callers should treat that as a no-op."""
        updates = {}
        for spec in self._fields:
            if not self._checks[spec.attr].isChecked():
                continue
            widget = self._widgets[spec.attr]
            if spec.kind in ("int", "float"):
                updates[spec.attr] = widget.value()
            elif spec.kind == "bool":
                updates[spec.attr] = widget.isChecked()
            elif spec.kind == "combo":
                updates[spec.attr] = widget.currentText()
        return updates
