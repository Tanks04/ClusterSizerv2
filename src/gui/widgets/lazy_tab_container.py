from typing import Callable

from PySide6.QtWidgets import QVBoxLayout, QWidget


class LazyTabContainer(QWidget):
    """Placeholder tab page that only builds the real widget the first
    time this tab actually becomes visible.

    Why: MainWindow used to construct all 8 pages up front (all their
    tables/models/proxies included), most of them staying hidden until
    the user clicked that tab. On Windows, the first real show of a
    widget that was fully built while hidden has repeatedly triggered a
    native "access violation" crash with no Python traceback (first with
    QHeaderView.ResizeToContents, and it kept happening after that was
    fixed too - once with QSortFilterProxyModel's deferred sort/layout
    work, most likely the same root cause: Qt/PySide defers layout work
    for hidden widgets, and something about catching up on that deferred
    work on Windows is unstable). Building each page only at the moment
    its tab is selected - never "hidden and constructed a while ago" -
    sidesteps the whole pattern instead of chasing which specific Qt call
    triggers it next.
    """

    def __init__(self, factory: Callable[[], QWidget]):
        super().__init__()
        self._factory = factory
        self.page: QWidget | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def ensure_built(self) -> None:
        if self.page is None:
            self.page = self._factory()
            self._layout.addWidget(self.page)
