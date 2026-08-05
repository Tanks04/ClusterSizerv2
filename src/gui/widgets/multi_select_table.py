from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView


class MultiSelectTableView(QTableView):
    """QTableView with built-in Ctrl/Shift multi-select, Delete key, and a
    right-click context menu (Edit/Copy/Delete). Shared component for all
    CRUD tables in the app (Servers/Storage/VMs/Network...).

    Deliberately does NOT use the persistent QHeaderView.ResizeToContents
    mode - that mode forces Qt to recompute column widths on EVERY model
    reset, and especially on the first real display of a tab that was
    constructed but stayed hidden until then (Qt defers layout for hidden
    widgets). That's a known-unstable combination on some Qt/PySide
    versions on Windows (access violation with no Python traceback at
    all). Instead: Interactive mode (the user manually resizes columns) +
    a one-shot deferred resizeColumnsToContents() after populating, called
    via auto_size_columns().
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
        """Compute column widths once, based on current content. Called
        after set_servers()/set_vms()/etc. Deferred via QTimer.singleShot,
        NOT called directly - so the calculation is guaranteed to land
        after Qt has finished the tab's show/layout cycle, not in the
        middle of it."""
        QTimer.singleShot(0, self._do_auto_size)

    def _do_auto_size(self) -> None:
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

    def selected_rows(self) -> list[int]:
        """Sorted, unique selected row indices."""
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
