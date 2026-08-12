import faulthandler
import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.services.project_service import ProjectService

CRASH_LOG_PATH = Path(__file__).parent / "crash.log"

# The open file handle MUST stay alive for the whole app lifetime
# (faulthandler writes to it directly at the OS level when a segfault
# happens) - that's why it's a module-level variable, not local to main().
_crash_log_file = None


def _enable_crash_diagnostics() -> None:
    """Catches two completely different kinds of "the app just disappears":

    1. A real native crash (segfault/abort in the Qt/C++ layer) -
       faulthandler writes the C stack + last Python frame directly to
       crash.log, even when the Python interpreter would otherwise never
       get a chance to print anything.
    2. An uncaught Python exception inside a Qt callback (e.g. in a
       model's data()/setData() method that Qt calls from C++) -
       sys.excepthook catches that too and writes to the same log, in
       case the console isn't visible (e.g. launched without a terminal).
    """
    global _crash_log_file
    _crash_log_file = open(CRASH_LOG_PATH, "a", encoding="utf-8", buffering=1)
    faulthandler.enable(file=_crash_log_file, all_threads=True)

    def _excepthook(exc_type, exc_value, exc_tb):
        _crash_log_file.write("\n--- Unhandled Python exception ---\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_crash_log_file)
        _crash_log_file.flush()
        # Still print to stderr too, in case the console is visible
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook



def _load_application_font(app: QApplication) -> None:
    """Load bundled Noto Sans so the UI does not depend on OS fonts."""
    fonts_dir = Path(__file__).parent / "src" / "resources" / "fonts"
    regular = QFontDatabase.addApplicationFont(
        str(fonts_dir / "NotoSans-Regular.ttf")
    )
    QFontDatabase.addApplicationFont(
        str(fonts_dir / "NotoSans-Bold.ttf")
    )

    families = QFontDatabase.applicationFontFamilies(regular) if regular >= 0 else []
    family = families[0] if families else "Noto Sans"
    app.setFont(QFont(family, 10))

def _load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "src" / "resources" / "styles" / "main.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> None:

    _enable_crash_diagnostics()

    app = QApplication(sys.argv)
    app.setApplicationName("ClusterSizer")

    _load_application_font(app)
    _load_stylesheet(app)

    project_service = ProjectService()

    window = MainWindow(project_service)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
