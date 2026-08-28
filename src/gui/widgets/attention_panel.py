from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from src.calculations.attention import AttentionItem
from src.calculations.thresholds import Status

_COLORS = {
    Status.CRITICAL: "#c62828",  # red
    Status.WARNING: "#ed6c02",   # orange
}


class AttentionPanel(QGroupBox):
    """Shows every current "needs attention" item (CPU/RAM/Storage
    oversubscription, N+1, DR Readiness, backup compliance, Maintenance
    expiry) in one place, or an all-clear message when there's nothing
    to flag - so a periodic review doesn't require clicking through
    every tab that computes one of these statuses individually."""

    def __init__(self, parent=None):
        super().__init__("Attention Needed", parent)
        self._layout = QVBoxLayout(self)
        self._item_labels: list[QLabel] = []

    def set_items(self, items: list[AttentionItem]) -> None:
        for label in self._item_labels:
            label.deleteLater()
        self._item_labels.clear()

        if not items:
            label = QLabel("\u2705 No issues found.")
            label.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self._layout.addWidget(label)
            self._item_labels.append(label)
            return

        for item in items:
            color = _COLORS.get(item.severity, "#757575")
            label = QLabel(f"\u2b24 {item.message}")
            label.setStyleSheet(f"color: {color};")
            label.setWordWrap(True)
            self._layout.addWidget(label)
            self._item_labels.append(label)
