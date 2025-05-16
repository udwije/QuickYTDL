# =========================
# app/signals.py
# =========================

from PyQt5.QtCore import QObject, pyqtSignal

class AppSignals(QObject):
    log_output = pyqtSignal(str)  # Emits logs to be shown in log tab
    update_status = pyqtSignal(int, str)  # row_index, new_status (emoji or label)
    progress_update = pyqtSignal(int, float)  # row_index, percent_complete
    fetch_complete = pyqtSignal(list)  # list of video metadata dictionaries
    fetch_error = pyqtSignal(str)  # emit error message if fetch fails
    download_finished = pyqtSignal(int, str)  # row_index, status
    all_downloads_complete = pyqtSignal()
