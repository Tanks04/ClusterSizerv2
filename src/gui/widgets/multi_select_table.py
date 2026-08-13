from typing import Callable

from PySide6.QtCore import Qt, QSortFilterProxyModel, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView


class MultiSelectTableView(QTableView):
    """QTableView with built-in Ctrl/Shift multi-select, Delete key, a
    right-click context menu (Edit/Copy/Delete), and working header-click
    sorting. Shared component for all CRUD tables in the app (Servers/
    Storage/VMs/Network...).

    Deliberately does NOT use the persistent QHeaderView.ResizeToContents
    mode - that mode forces Qt to recompute column widths on EVERY model
    reset, and especially on the first real display of a tab that was
    constructed but stayed hidden until then (Qt defers layout for hidden
    widgets). That's a known-unstable combination on some Qt/PySide
    versions on Windows (access violation with no Python traceback at
    all). Instead: Interactive mode (the user manually resizes columns) +
    a one-shot deferred resizeColumnsToContents() after populating, called
    via auto_size_columns().

    Sorting: setSortingEnabled(True) alone only shows the header arrow -
    a plain QAbstractTableModel doesn't implement sort() itself, so
    clicking a header does nothing to the row order. Call
    set_source_model() instead of setModel() directly to get real
    click-to-sort behaviour, via an internal QSortFilterProxyModel.
    """

    delete_requested = Signal()
    copy_requested = Signal()
    edit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._proxy: QSortFilterProxyModel | None = None
        self._custom_actions: list[tuple[str, "Callable[[], None]"]] = []

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

    def set_source_model(self, model) -> None:
        """Wraps `model` in a QSortFilterProxyModel and sets that as the
        view's model, so header clicks actually reorder rows. Use this
        instead of setModel() for every CRUD table - selected_rows() below
        transparently maps proxy rows back to source-model rows, so page
        code (self.model.server_at(row), etc.) never needs to know a proxy
        is involved."""
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setDynamicSortFilter(True)
        self.setModel(proxy)
        self._proxy = proxy

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

    def set_custom_actions(self, actions: list[tuple[str, "Callable[[], None]"]]) -> None:
        """Extra context-menu actions specific to this page's entity type
        (e.g. the VMs page adding "Mark DR Protected") - kept out of this
        shared widget's own signal set so Servers/Storage/Network pages
        aren't forced to know about VM-only concepts. Each entry is
        (label, no-arg callback); shown after Copy and before Delete,
        same "only when something's selected" rule as the built-in
        actions. Replaces any previously set custom actions."""
        self._custom_actions = list(actions)

    def selected_rows(self) -> list[int]:
        """Sorted, unique selected row indices - always relative to the
        SOURCE model, even if the view is currently sorted (translated
        through the proxy set up by set_source_model())."""
        rows = set()
        for index in self.selectionModel().selectedRows():
            if self._proxy is not None:
                index = self._proxy.mapToSource(index)
            rows.add(index.row())
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

        if self._custom_actions:
            menu.addSeparator()
            for label, callback in self._custom_actions:
                action = menu.addAction(label)
                action.triggered.connect(callback)

        menu.addSeparator()

        delete_action = menu.addAction(f"🗑 Delete{count_suffix}")
        delete_action.triggered.connect(self.delete_requested.emit)

        menu.exec(self.viewport().mapToGlobal(pos))
