# quickytdl/main.py

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QLoggingCategory
from PyQt6.QtGui import QIcon
from quickytdl.ui.main_window import MainWindow

def main():
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
