# quickytdl/ui/main_window.py

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLineEdit, QComboBox, QPushButton, 
    QTableView, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QCheckBox, QLabel
)
from PyQt6.QtCore import pyqtSlot, Qt

#from quickytdl.models import PlaylistTableModel, DownloadTableModel
#from quickytdl.fetcher import PlaylistFetcher
#from quickytdl.manager import DownloadManager
#from quickytdl.config import ConfigManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickYTDL")
        self.resize(1000, 700)

        # ── load user settings ───────────────────────────────────────────────────
        self.config = ConfigManager()
        self.config.load()

        # ── core components ──────────────────────────────────────────────────────
        self.fetcher = PlaylistFetcher()
        self.manager = DownloadManager()

        # ── table models ─────────────────────────────────────────────────────────
        self.fetchModel    = PlaylistTableModel([])
        self.downloadModel = DownloadTableModel([])

        # ── build out the UI ─────────────────────────────────────────────────────
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        # central widget + main vertical layout
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        # ── Tab widget ─────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # --- 1) QuickYTDL tab ─────────────────────────────────────────────────
        tab_main = QWidget()
        main_layout = QVBoxLayout(tab_main)

        # URL input / format selector / Fetch button
        hl_url = QHBoxLayout()
        self.urlEdit     = QLineEdit()
        self.urlEdit.setPlaceholderText("Playlist URL")
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["1080p", "720p", "480p", "360p"])
        self.fetchBtn    = QPushButton("Fetch")
        hl_url.addWidget(self.urlEdit)
        hl_url.addWidget(self.formatCombo)
        hl_url.addWidget(self.fetchBtn)
        main_layout.addLayout(hl_url)

        # Fetched playlist table
        self.fetchTable = QTableView()
        self.fetchTable.setModel(self.fetchModel)
        main_layout.addWidget(self.fetchTable)

        # Save-location + Download / Cancel buttons
        hl_save = QHBoxLayout()
        hl_save.addWidget(QLabel("Save Location:"))
        self.saveEdit    = QLineEdit(self.config.default_save_dir)
        self.browseBtn   = QPushButton("Browse")
        self.downloadBtn = QPushButton("Download")
        self.cancelBtn   = QPushButton("Cancel")
        hl_save.addWidget(self.saveEdit)
        hl_save.addWidget(self.browseBtn)
        hl_save.addWidget(self.downloadBtn)
        hl_save.addWidget(self.cancelBtn)
        main_layout.addLayout(hl_save)

        # Download status table
        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        main_layout.addWidget(self.downloadTable)

        self.tabs.addTab(tab_main, "QuickYTDL")

        # --- 2) Log tab ───────────────────────────────────────────────────────
        tab_log = QWidget()
        log_layout = QVBoxLayout(tab_log)
        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        log_layout.addWidget(self.logView)
        self.tabs.addTab(tab_log, "Log")

        # --- 3) Options tab ───────────────────────────────────────────────────
        tab_opt = QWidget()
        opt_layout = QVBoxLayout(tab_opt)
        self.autoShutdownChk = QCheckBox("Auto shutdown when complete")
        opt_layout.addWidget(self.autoShutdownChk)

        hl_def = QHBoxLayout()
        hl_def.addWidget(QLabel("Default Save Location:"))
        self.defSaveEdit  = QLineEdit(self.config.default_save_dir)
        self.defBrowseBtn = QPushButton("Browse")
        hl_def.addWidget(self.defSaveEdit)
        hl_def.addWidget(self.defBrowseBtn)
        opt_layout.addLayout(hl_def)

        self.tabs.addTab(tab_opt, "Options")

    def _connect_signals(self):
        # button clicks
        self.fetchBtn.clicked.connect(self.on_fetch_clicked)
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)

        # download manager signals
        self.manager.progress.connect(self.on_download_progress)
        self.manager.finished.connect(self.on_download_finished)

        # optional logging from fetcher/manager
        self.fetcher.log.connect(self.logView.append)
        self.manager.log.connect(self.logView.append)

    @pyqtSlot()
    def on_fetch_clicked(self):
        url = self.urlEdit.text().strip()
        if not url:
            return
        items = self.fetcher.fetch_playlist(url)
        self.fetchModel.set_items(items)

    @pyqtSlot()
    def on_browse_save(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.saveEdit.text()
        )
        if directory:
            self.saveEdit.setText(directory)

    @pyqtSlot()
    def on_browse_default(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Save Directory", self.defSaveEdit.text()
        )
        if directory:
            self.defSaveEdit.setText(directory)
            self.config.default_save_dir = directory
            self.config.save()

    @pyqtSlot()
    def on_download_clicked(self):
        selected = self.fetchModel.get_selected_items()
        if not selected:
            return
        save_dir = self.saveEdit.text().strip() or self.config.default_save_dir
        self.downloadModel.set_items(selected)
        self.manager.start_downloads(selected, save_dir)

    @pyqtSlot()
    def on_cancel_clicked(self):
        self.manager.cancel_all()

    @pyqtSlot(int, float, str)
    def on_download_progress(self, index, percent, status):
        self.downloadModel.update_progress(index, percent, status)

    @pyqtSlot(int, str)
    def on_download_finished(self, index, status):
        self.downloadModel.update_status(index, status)

        # if everything’s done and user wants auto‐shutdown:
        all_statuses = self.downloadModel.get_statuses()
        if all(s in ("Completed", "Skipped") for s in all_statuses):
            if self.autoShutdownChk.isChecked():
                # Windows
                os.system("shutdown /s /t 60")
                # (or use cross‐platform approaches if desired)
