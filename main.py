# main.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QLoggingCategory
from quickytdl.ui.main_window import MainWindow
from PyQt6.QtGui import QIcon
import quickytdl.resources_rc  # make sure your .qrc has been compiled

def main():
    # suppress Qt paint/font warnings
    QLoggingCategory.setFilterRules(
        "qt.qpa.*=false\n"
        "qt.text.font.db=false"
    )
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(":/QuickYTDL.ico"))  # set taskbar & window icon
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
