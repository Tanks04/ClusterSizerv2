from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGroupBox, QLabel, QMenu, QVBoxLayout

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
    every tab that computes one of these statuses individually.
    Right-click any item to copy it (or all of them) - e.g. into an
    email to whoever needs to see it."""

    def __init__(self, parent=None):
        super().__init__("ATTENTION NEEDED", parent)
        self.setStyleSheet(
            "QGroupBox::title { font-weight: bold; }"
        )
        self._layout = QVBoxLayout(self)
        self._item_labels: list[QLabel] = []
        self._messages: list[str] = []

    def _show_context_menu(self, pos, message: str) -> None:
        label = self.sender()
        menu = QMenu(self)
        menu.addAction("Copy This Item", lambda: QGuiApplication.clipboard().setText(message))
        if len(self._messages) > 1:
            menu.addAction(
                "Copy All Items",
                lambda: QGuiApplication.clipboard().setText("\n".join(self._messages)),
            )
        menu.exec(label.mapToGlobal(pos))

    def set_items(self, items: list[AttentionItem]) -> None:
        for label in self._item_labels:
            label.deleteLater()
        self._item_labels.clear()
        self._messages = [item.message for item in items]

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
            label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            label.customContextMenuRequested.connect(
                lambda pos, msg=item.message: self._show_context_menu(pos, msg)
            )
            self._layout.addWidget(label)
            self._item_labels.append(label)
