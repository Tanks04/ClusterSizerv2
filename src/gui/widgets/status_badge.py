from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from src.calculations.thresholds import Status

_COLORS = {
    Status.OK: "#2e7d32",        # green
    Status.WARNING: "#ed6c02",   # orange
    Status.CRITICAL: "#c62828",  # red
    Status.UNKNOWN: "#757575",   # gray
}


class StatusBadge(QLabel):
    """Small colored status badge (OK / Warning / Critical / Unknown)."""

    def __init__(self, status: Status = Status.UNKNOWN, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: Status) -> None:
        color = _COLORS.get(status, _COLORS[Status.UNKNOWN])
        self.setText(status.value)
        self.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 6px;"
            f"padding: 3px 10px; font-weight: bold;"
        )
