"""App-wide accent color - controls the selection highlight color
(table row selection, list selection, text selection) across the
whole app. Called once at startup (main.py) and again live whenever
the person changes it on Settings - no restart needed.

Sets QPalette.Highlight AND injects an explicit QSS override for
QAbstractItemView selection. Both are needed: QPalette alone isn't
enough because some native OS styles (Windows' "windowsvista",
macOS's native style) don't reliably honor QPalette.Highlight for
table/list row selection regardless of what the palette says -
reported directly (picking green or red, selection stayed the
platform's default blue). The QSS rule below is honored the same way
everywhere Qt runs, so it's the one that actually guarantees the
color changes.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_ACCENT_QSS_START = "/* === accent color override (auto-generated) === */"
_ACCENT_QSS_END = "/* === end accent color override === */"


def _accent_qss_block(hex_color: str) -> str:
    return (
        f"{_ACCENT_QSS_START}\n"
        f"QTableView::item:selected, QListView::item:selected, QTreeView::item:selected {{\n"
        f"    background-color: {hex_color};\n"
        f"    color: #ffffff;\n"
        f"}}\n"
        f"{_ACCENT_QSS_END}"
    )


def apply_accent_color(app: QApplication, hex_color: str) -> None:
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(hex_color))
    # White reads well against most reasonably-saturated accent colors -
    # a full contrast calculation would be more thorough, but this
    # matches how most apps handle a single configurable accent color.
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    current = app.styleSheet()
    if _ACCENT_QSS_START in current and _ACCENT_QSS_END in current:
        start = current.index(_ACCENT_QSS_START)
        end = current.index(_ACCENT_QSS_END) + len(_ACCENT_QSS_END)
        current = current[:start] + current[end:]
    app.setStyleSheet(current.rstrip() + "\n\n" + _accent_qss_block(hex_color))
