from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView


class MultiSelectTableView(QTableView):
    """QTableView s ugrađenim Ctrl/Shift multi-selectom, Delete tipkom i
    desni-klik kontekstnim menijem (Edit/Copy/Delete). Zajednička komponenta
    za sve CRUD tablice u aplikaciji (Servers/Storage/VMs/Network...).

    Namjerno NE koristi trajni QHeaderView.ResizeToContents mod - taj mod
    prisiljava Qt da preračuna širine stupaca pri SVAKOM model resetu, a
    pogotovo pri prvom stvarnom prikazu taba koji je do tad bio konstruiran
    ali skriven (Qt odgađa layout skrivenih widgeta). To je poznato
    nestabilna kombinacija na nekim Qt/PySide verzijama na Windowsima
    (access violation bez ikakvog Python tracebacka). Umjesto toga:
    Interactive mod (korisnik ručno širi kolone) + jednokratni odgođeni
    resizeColumnsToContents() nakon populacije, pozvan preko auto_size_columns().
    """

    delete_requested = Signal()
    copy_requested = Signal()
    edit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.doubleClicked.connect(lambda _: self.edit_requested.emit())

    def auto_size_columns(self) -> None:
        """Jednom izračunaj širine stupaca prema trenutnom sadržaju. Zove se
        nakon set_servers()/set_vms()/itd. Odgođeno preko QTimer.singleShot,
        NE direktno - da izračun sigurno padne u trenutak kad je Qt već
        završio show/layout ciklus taba, ne usred njega."""
        QTimer.singleShot(0, self._do_auto_size)

    def _do_auto_size(self) -> None:
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

    def selected_rows(self) -> list[int]:
        """Sortirane, jedinstvene selektirane row-indekse."""
        rows = {index.row() for index in self.selectionModel().selectedRows()}
        return sorted(rows)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.selected_rows():
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)

    def _show_context_menu(self, pos) -> None:
        rows = self.selected_rows()
        if not rows:
            return

        menu = QMenu(self)

        if len(rows) == 1:
            edit_action = menu.addAction("✏ Edit")
            edit_action.triggered.connect(self.edit_requested.emit)

        count_suffix = f" ({len(rows)})" if len(rows) > 1 else ""

        copy_action = menu.addAction(f"📄 Copy{count_suffix}")
        copy_action.triggered.connect(self.copy_requested.emit)

        menu.addSeparator()

        delete_action = menu.addAction(f"🗑 Delete{count_suffix}")
        delete_action.triggered.connect(self.delete_requested.emit)

        menu.exec(self.viewport().mapToGlobal(pos))
