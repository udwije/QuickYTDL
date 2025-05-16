# =========================
# app/widgets/format_selector.py
# =========================
from PyQt5.QtWidgets import QComboBox

class FormatSelector(QComboBox):
    def __init__(self):
        super().__init__()
        self.addItems(["360p", "480p", "720p", "1080p", "audio-only"])