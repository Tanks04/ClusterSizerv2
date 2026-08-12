import copy
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.calculations.comparison import (
    build_comparison_rows, build_delta_summary, projects_are_identical,
)
from src.models.cluster_project import ClusterProject
from src.persistence import project_repository
from src.persistence.project_repository import FILE_EXTENSION
from src.services.project_service import ProjectService

from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.error_handling import report_error

SECTION_BG = QColor("#eceff1")
DIFF_BG = QColor("#fff8e1")


class ComparePage(QWidget):
    """Compares two scenarios side by side. Both slots are loaded
    explicitly and independently - neither is silently tied to whatever
    project happens to be open elsewhere in the app, so what you're
    comparing never changes underneath you. "Use Current Project" is a
    shortcut into either slot when you just want to snapshot what's open
    right now, without a save-to-disk round trip first."""

    def __init__(self, service: ProjectService):
        super().__init__()

        self.service = service
        self.scenario_a: ClusterProject | None = None
        self.scenario_a_label = ""
        self.scenario_b: ClusterProject | None = None
        self.scenario_b_label = ""

        self._create_ui()

        # Loaded scenarios are static snapshots - we only need to react to
        # threshold changes (Settings page), which apply uniformly to
        # whatever's currently loaded, not to project data changing.
        self.service.changed.connect(self._refresh)
        self._refresh()

    def _create_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Compare Scenarios")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title.setFont(title_font)
        layout.addWidget(title)

        info = QLabel(
            "Load two .clsz files (or snapshot what's currently open) into "
            "Scenario A and B to compare them - both slots are independent "
            "snapshots, so nothing here changes just because you edit "
            "something on another tab."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #757575; font-style: italic;")
        layout.addWidget(info)

        slots_row = QHBoxLayout()
        slots_row.addLayout(self._build_slot_controls("A", self._load_scenario_a, self._use_current_a))
        slots_row.addLayout(self._build_slot_controls("B", self._load_scenario_b, self._use_current_b))
        layout.addLayout(slots_row)

        self.identical_warning_label = QLabel("")
        self.identical_warning_label.setWordWrap(True)
        self.identical_warning_label.setStyleSheet(
            "background-color: #fff3cd; color: #664d03; padding: 8px; border-radius: 4px;"
        )
        self.identical_warning_label.setVisible(False)
        layout.addWidget(self.identical_warning_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        delta_label = QLabel("At a glance (B \u2212 A):")
        delta_label_font = delta_label.font()
        delta_label_font.setBold(True)
        delta_label.setFont(delta_label_font)
        layout.addWidget(delta_label)

        delta_row = QHBoxLayout()
        self.delta_cards: list[SummaryWidget] = []
        for label in ("\u0394 Servers", "\u0394 Cores", "\u0394 RAM (GB)", "\u0394 VMs", "\u0394 Storage (TB)"):
            card = SummaryWidget(label, "-", compact=True)
            self.delta_cards.append(card)
            delta_row.addWidget(card)
        layout.addLayout(delta_row)

    def _build_slot_controls(self, slot_name: str, load_fn, use_current_fn) -> QVBoxLayout:
        box = QVBoxLayout()

        label = QLabel(f"Scenario {slot_name}")
        label_font = label.font()
        label_font.setBold(True)
        label.setFont(label_font)
        box.addWidget(label)

        buttons = QHBoxLayout()
        load_button = QPushButton(f"\U0001F4C2 Load {slot_name}...")
        load_button.clicked.connect(load_fn)
        buttons.addWidget(load_button)

        current_button = QPushButton("Use Current Project")
        current_button.clicked.connect(use_current_fn)
        buttons.addWidget(current_button)
        box.addLayout(buttons)

        status_label = QLabel("(none loaded)")
        status_label.setStyleSheet("color: #757575;")
        box.addWidget(status_label)

        if slot_name == "A":
            self.scenario_a_status_label = status_label
        else:
            self.scenario_b_status_label = status_label

        return box

    # ------------------------------------------------------------------
    # Loading scenarios
    # ------------------------------------------------------------------

    def _load_scenario_a(self):
        self._load_into("A")

    def _load_scenario_b(self):
        self._load_into("B")

    def _use_current_a(self):
        self.scenario_a = copy.deepcopy(self.service.project)
        self.scenario_a_label = f"{self.service.project.name} (current, snapshot)"
        self._refresh()

    def _use_current_b(self):
        self.scenario_b = copy.deepcopy(self.service.project)
        self.scenario_b_label = f"{self.service.project.name} (current, snapshot)"
        self._refresh()

    def _load_into(self, slot_name: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Load Scenario {slot_name}", "", f"ClusterSizer Project (*{FILE_EXTENSION})"
        )
        if not path:
            return
        try:
            project = project_repository.load_project(path).project
        except Exception as exc:
            report_error(self, "Load Error", exc)
            return

        if slot_name == "A":
            self.scenario_a = project
            self.scenario_a_label = Path(path).name
        else:
            self.scenario_b = project
            self.scenario_b_label = Path(path).name
        self._refresh()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _refresh(self):
        thresholds = self.service.thresholds

        self.scenario_a_status_label.setText(self.scenario_a_label or "(none loaded)")
        self.scenario_b_status_label.setText(self.scenario_b_label or "(none loaded)")

        if self.scenario_a is None or self.scenario_b is None:
            self.identical_warning_label.setVisible(False)
            self.table.setRowCount(0)
            self.table.setHorizontalHeaderLabels(["Metric", "Scenario A", "Scenario B"])
            for card in self.delta_cards:
                card.set_value("-")
            return

        if projects_are_identical(self.scenario_a, self.scenario_b):
            self.identical_warning_label.setText(
                "\u26a0 Scenario A and Scenario B are identical - there's nothing to "
                "compare. Load a different file into one of the slots, or make changes "
                "to your active project and snapshot it again with 'Use Current Project'."
            )
            self.identical_warning_label.setVisible(True)
        else:
            self.identical_warning_label.setVisible(False)

        rows = build_comparison_rows(self.scenario_a, self.scenario_b, thresholds)
        self._populate_table(rows)

        deltas = build_delta_summary(self.scenario_a, self.scenario_b)
        for card, (_, value) in zip(self.delta_cards, deltas):
            card.set_value(value)

    def _populate_table(self, rows: list[tuple[str, str, str]]):
        self.table.setHorizontalHeaderLabels([
            "Metric", f"A: {self.scenario_a_label}", f"B: {self.scenario_b_label}",
        ])
        self.table.setRowCount(len(rows))

        bold_font = QFont()
        bold_font.setBold(True)

        for row_index, (label, val_a, val_b) in enumerate(rows):
            is_section = label.startswith("---")
            is_diff = not is_section and val_a != val_b

            item_label = QTableWidgetItem(label)
            item_a = QTableWidgetItem(val_a)
            item_b = QTableWidgetItem(val_b)

            for item in (item_label, item_a, item_b):
                if is_section or is_diff:
                    item.setFont(bold_font)
                if is_section:
                    item.setBackground(SECTION_BG)
                elif is_diff:
                    item.setBackground(DIFF_BG)

            item_a.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_b.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row_index, 0, item_label)
            self.table.setItem(row_index, 1, item_a)
            self.table.setItem(row_index, 2, item_b)

        # One-shot column-0 width computation, deferred to the next event
        # loop tick - NOT a persistent ResizeToContents mode. See
        # MultiSelectTableView's docstring for why persistent
        # ResizeToContents is avoided everywhere else in this app (the
        # Windows access-violation crash hunt, v2.0.x-v2.1.1).
        QTimer.singleShot(0, lambda: self.table.resizeColumnToContents(0))
