# =========================
# app/main_window.py
# =========================

from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog,
    QTabWidget, QLabel, QHBoxLayout, QLineEdit, QComboBox
)
from app.widgets.playlist_table import PlaylistTable
from app.widgets.log_tab import LogTab
from app.fetcher import Fetcher
from app.downloader import DownloadManager
from app.signals import AppSignals
from app.utils import get_format_options


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickYTDL")
        self.resize(800, 600)

        # Components
         

        self.signals = AppSignals()
        self.fetcher = Fetcher(self.signals) 
        self.download_manager = DownloadManager(self.signals)

        self._init_ui()
        self._connect_signals()
        
    def _init_ui(self):
        # URL and Format Row
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube video or playlist URL here...")

        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(get_format_options())

        input_layout.addWidget(QLabel("URL:"))
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(QLabel("Format:"))
        input_layout.addWidget(self.format_dropdown)

        # Buttons
        self.fetch_button = QPushButton("Fetch")
        self.download_button = QPushButton("Download")
        self.cancel_button = QPushButton("Cancel")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.fetch_button)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)

        # Tabs: Playlist Table + Log View
        self.playlist_table = PlaylistTable()
        self.signals.fetch_complete.connect(self.playlist_table.populate_table)
        self.log_tab = LogTab()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.playlist_table, "Playlist")
        self.tabs.addTab(self.log_tab, "Logs")

        # Main Layout
        layout = QVBoxLayout()
        layout.addLayout(input_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _connect_signals(self):
        self.fetch_button.clicked.connect(self.handle_fetch_clicked)
        self.download_button.clicked.connect(self.handle_download_clicked)
        self.cancel_button.clicked.connect(self.handle_cancel_clicked)

        self.signals.log_output.connect(self.log_tab.append_log)
        self.signals.update_status.connect(self.playlist_table.update_status)
        self.signals.progress_update.connect(self.playlist_table.update_progress_bar)

    def handle_fetch_clicked(self):
        url = self.url_input.text().strip()
        if url:
            selected_format = self.format_dropdown.currentText()
            self.fetcher.fetch_playlist_metadata(url)


    def handle_download_clicked(self):
        selected_items = self.playlist_table.get_selected_items()
        if selected_items:
            selected_format = self.format_dropdown.currentText()
            self.download_manager.start_downloads(selected_items, selected_format)

    def handle_cancel_clicked(self):
        self.download_manager.cancel_all()
