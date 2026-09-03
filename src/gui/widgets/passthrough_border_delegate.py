from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPen
from PySide6.QtCore import Qt

from src.gui.models.vm_table_model import PASSTHROUGH_BORDER_COLOR_ROLE


class PassthroughBorderDelegate(QStyledItemDelegate):
    """Draws a colored border (not a filled background) around every
    cell in a VM's row that has at least one PCI-passthrough storage
    pool connected to it - visible at a glance without losing the
    normal cell content/selection highlight underneath. Same technique
    as RedundancyBorderDelegate on the Switches table, kept as a
    separate small class rather than sharing one across two unrelated
    table models.

    Reads the color via index.data(PASSTHROUGH_BORDER_COLOR_ROLE)
    rather than indexing into the model directly - this way Qt
    resolves the correct row whether the view displays the model
    directly or through a QSortFilterProxyModel wrapping it."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        color = index.data(PASSTHROUGH_BORDER_COLOR_ROLE)
        if color is None:
            return

        painter.save()
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
        painter.restore()
