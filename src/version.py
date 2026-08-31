"""Single source of truth for the app version - imported by main_window.py
(window title, About box, status bar) and reports_page.py (PDF/text report
stamps), so it's never hardcoded a second place. A dedicated module,
rather than reports_page.py importing MainWindow.VERSION directly, avoids
a circular import (main_window.py imports ReportsPage)."""

VERSION = "4.5.1"
