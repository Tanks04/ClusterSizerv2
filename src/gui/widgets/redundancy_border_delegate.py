from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPen
from PySide6.QtCore import Qt

from src.gui.models.switch_table_model import REDUNDANCY_BORDER_COLOR_ROLE


class RedundancyBorderDelegate(QStyledItemDelegate):
    """Draws a colored border (not a filled background) around every
    cell in a row whose switch has a redundancy_group set - two paired
    switches (an HSRP pair, an Active/Passive firewall HA pair, an
    MLAG/VPC stack) get a matching-color outline around their entire
    row, so the pairing is visible at a glance without losing the
    normal cell content/selection highlight underneath.

    Reads the color via index.data(REDUNDANCY_BORDER_COLOR_ROLE) rather
    than indexing into the model directly - this way Qt resolves the
    correct row whether the view displays the model directly or
    through a QSortFilterProxyModel wrapping it."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        color = index.data(REDUNDANCY_BORDER_COLOR_ROLE)
        if color is None:
            return

        painter.save()
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
        painter.restore()
