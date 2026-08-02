import faulthandler
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.services.project_service import ProjectService

CRASH_LOG_PATH = Path(__file__).parent / "crash.log"

# Handle na otvorenu datoteku MORA ostati živ cijelo vrijeme rada aplikacije
# (faulthandler piše u nju izravno na OS razini kad se dogodi segfault) -
# zato je modulska varijabla, ne lokalna unutar main().
_crash_log_file = None


def _enable_crash_diagnostics() -> None:
    """Hvata dvije potpuno različite vrste "aplikacija samo nestane":

    1. Pravi native crash (segfault/abort u Qt/C++ sloju) - faulthandler
       ispisuje C stack + zadnji Python frame direktno u crash.log, čak i
       kad Python interpreter inače ne bi stigao ništa ispisati.
    2. Neuhvaćena Python iznimka unutar Qt callbacka (npr. u modelovoj
       data()/setData() metodi koju Qt poziva iz C++) - sys.excepthook
       hvata i to i piše u isti log, za slučaj da konzola nije vidljiva
       (npr. pokretanje bez terminala).
    """
    global _crash_log_file
    _crash_log_file = open(CRASH_LOG_PATH, "a", encoding="utf-8", buffering=1)
    faulthandler.enable(file=_crash_log_file, all_threads=True)

    def _excepthook(exc_type, exc_value, exc_tb):
        _crash_log_file.write("\n--- Unhandled Python exception ---\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_crash_log_file)
        _crash_log_file.flush()
        # I dalje ispiši i na stderr ako je konzola vidljiva
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


def _load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "src" / "resources" / "styles" / "main.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> None:

    _enable_crash_diagnostics()

    app = QApplication(sys.argv)
    app.setApplicationName("ClusterSizer")

    _load_stylesheet(app)

    project_service = ProjectService()

    window = MainWindow(project_service)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
