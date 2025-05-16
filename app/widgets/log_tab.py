# =========================
# app/widgets/log_tab.py
# =========================
from PyQt5.QtWidgets import QTextEdit

class LogTab(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)

    def append_log(self, message):
        self.append(message)