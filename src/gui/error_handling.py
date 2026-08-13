"""Shared error-reporting helper for GUI exception handlers.

Every `except Exception as exc:` handler in the app used to just show
`str(exc)` in a QMessageBox and discard the traceback - so a user-facing
"KeyError: 'name'" left nothing for the crash log to have caught,
despite the app having crash-log infrastructure (see main.py). Use
report_error() instead of QMessageBox.critical(..., str(exc)) so a full
traceback survives.
"""

import traceback
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from src.persistence.csv_io import CsvSchemaError
from src.persistence.generic_import import UnsupportedFileError

# Same location as main.py's CRASH_LOG_PATH and import_profile_store's
# PROFILES_PATH - the app's per-user config/log home. Kept as its own
# constant (not imported from main.py) to avoid a GUI module importing
# the entry-point module.
_LOG_PATH = Path.home() / ".clustersizer" / "crash.log"

# These two carry their own human-authored, already-actionable messages
# (CsvSchemaError names the missing columns; UnsupportedFileError explains
# a missing optional dependency or bad file format) - str(exc) IS the
# right thing to show for them. Anything else is an unexpected exception
# whose repr (KeyError: 'name', etc.) means nothing to the person reading
# the dialog - show a generic message instead and point at the log.
_MESSAGE_CARRYING_EXCEPTION_TYPES = (CsvSchemaError, UnsupportedFileError)


def report_error(parent: QWidget | None, title: str, exc: Exception) -> None:
    """Logs the full traceback for `exc` to the crash log (best-effort -
    a logging failure here must never mask the original error or raise
    past this function). Shows str(exc) for the app's own message-
    carrying exception types (already readable); shows a generic
    "something went wrong, check the log" message for anything else,
    instead of a raw Python exception repr."""
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n--- {title} ---\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
    except OSError:
        pass

    if isinstance(exc, _MESSAGE_CARRYING_EXCEPTION_TYPES):
        QMessageBox.critical(parent, title, str(exc))
    else:
        QMessageBox.critical(
            parent, title,
            f"Something went wrong. Details were saved to:\n{_LOG_PATH}",
        )
