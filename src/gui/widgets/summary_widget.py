from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class SummaryWidget(QFrame):
    """
    Small dashboard card used to display summary values.

    Example:
        Servers
            4

        RAM
        2048 GB
    """

    def __init__(self, title: str, value: str = "0", parent=None, compact: bool = False):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("SummaryWidget")

        self.setMinimumHeight(55 if compact else 110)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)
        margin = 6 if compact else 12
        layout.setContentsMargins(margin, margin, margin, margin)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(8 if compact else 10)

        self.title_label.setFont(title_font)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_font = QFont()
        value_font.setBold(True)
        value_font.setPointSize(11 if compact else 20)

        self.value_label.setFont(value_font)

        layout.addWidget(self.title_label)
        if not compact:
            layout.addStretch()
        layout.addWidget(self.value_label)

    def set_value(self, value: str | int | float) -> None:
        self.value_label.setText(str(value))


