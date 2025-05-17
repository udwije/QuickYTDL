# =========================
# main.py
# =========================
"""
import sys
from PyQt6.QtWidgets import QApplication
from quickytdl.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
"""

# main.py
import sys, os

print("CWD:", os.getcwd())
print("sys.path[0]:", sys.path[0])
print("Available packages in root:", os.listdir(os.getcwd()))
print("quickytdl folder contents:", os.listdir(os.path.join(os.getcwd(), "quickytdl")))
print()

# now do the real import
from PyQt6.QtWidgets import QApplication
from quickytdl.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
