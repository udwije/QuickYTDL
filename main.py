# quickytdl/main.py

import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QLoggingCategory
from PyQt6.QtGui import QIcon
from quickytdl.ui.main_window import MainWindow


def _install_crash_guard():
    """
    PyQt6's default behavior for an unhandled Python exception raised inside
    any Qt-invoked callback (a slot, a QThread.run() override, a delegate's
    paint(), etc.) is to print the traceback and then call abort(), killing
    the whole application instantly with no chance to recover.

    We can't stop Qt from tearing down whatever specific operation failed,
    but we CAN stop it from nuking the entire app: replacing sys.excepthook
    just logs the error instead of letting it fall through to Qt's fatal
    handler for anything that still slips past our own try/excepts.
    """
    def _handle(exc_type, exc_value, exc_tb):
        print("⚠️  Unhandled exception (app kept running):", file=sys.stderr)
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle


def main():
    _install_crash_guard()

    # suppress Qt paint/font warnings
    QLoggingCategory.setFilterRules(
        "qt.qpa.*=false\n"
        "qt.text.font.db=false"
    )

    app = QApplication(sys.argv)

    # Set the application icon from resources
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "QuickYTDL.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    # Set window-level icon as well
    window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
