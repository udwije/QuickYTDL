# quickytdl/ui/main_window.py

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLineEdit, QComboBox, QPushButton,
    QTableView, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QCheckBox, QLabel, QMessageBox,
    QStyledItemDelegate, QHeaderView
)
from PyQt6.QtCore import pyqtSlot, Qt, QThread, QObject, pyqtSignal

from quickytdl.models import PlaylistTableModel, DownloadTableModel
from quickytdl.fetcher import PlaylistFetcher
from quickytdl.manager import DownloadManager
from quickytdl.config import ConfigManager
from quickytdl.utils import ensure_directory


class FormatDelegate(QStyledItemDelegate):
    """
    Delegate to render a QComboBox in the 'Format' column for each row,
    allowing per-video format selection.
    """
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        item = index.model()._items[index.row()]
        combo.addItems(item.available_formats)
        return combo

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data(Qt.ItemDataRole.EditRole))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

class ProgressBarDelegate(QStyledItemDelegate):
    """
    Renders a progress bar with centered percentage text for the download table.
    """
    def paint(self, painter, option, index):
        value = int(index.data())
        from PyQt6.QtWidgets import QStyleOptionProgressBar, QApplication, QStyle
        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = value
        opt.text = f"{value}%"
        opt.textVisible = True
        opt.textAlignment = Qt.AlignmentFlag.AlignCenter
        painter.save()
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opt, painter)
        painter.restore()

class FetchWorker(QObject):
    """
    Offloads playlist metadata fetching into its own thread.
    """
    fetch_request = pyqtSignal(str)   # queued request to start fetch
    finished      = pyqtSignal(list)  # emits list[VideoItem]
    error         = pyqtSignal(str)   # emits any error message
    log           = pyqtSignal(str)   # passes through fetcher log messages

    def __init__(self, fetcher: PlaylistFetcher):
        super().__init__()
        self.fetcher = fetcher
        # queue fetch calls in this thread
        self.fetch_request.connect(self._on_fetch, Qt.ConnectionType.QueuedConnection)
        # forward detailed logs into this worker's 'log' signal
        self.fetcher.log.connect(self.log)

    @pyqtSlot(str)
    def _on_fetch(self, url: str):
        try:
            items = self.fetcher.fetch_playlist(url)
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickYTDL")
        self.resize(1000, 700)

        # ── Load or initialize user settings ──────────────────────────
        self.config = ConfigManager()
        self.config.load()
        if not os.path.isdir(self.config.default_save_dir):
            self._prompt_for_default_folder()

        # ── Core components ──────────────────────────────────────────
        self.fetcher = PlaylistFetcher()
        self.manager = DownloadManager()

        # ── Data models ──────────────────────────────────────────────
        self.fetchModel    = PlaylistTableModel([])
        self.downloadModel = DownloadTableModel([])

        # ── Build UI and hook up signals ─────────────────────────────
        self._build_ui()
        self._connect_signals()
        self.autoShutdownChk.setChecked(self.config.auto_shutdown)

        # placeholders for dynamic fetch thread & worker
        self._fetch_thread = None
        self._fetch_worker = None

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # --- Main download tab ---
        tab_main = QWidget()
        ml = QVBoxLayout(tab_main)

        # URL input + Fetch button (no format here)
        h1 = QHBoxLayout()
        self.urlEdit  = QLineEdit()
        self.urlEdit.setPlaceholderText("Playlist URL")
        self.fetchBtn = QPushButton("Fetch")
        h1.addWidget(self.urlEdit)
        h1.addWidget(self.fetchBtn)
        ml.addLayout(h1)

        # Select-All checkbox above the table
        self.selectAllChk = QCheckBox("Select All")
        ml.addWidget(self.selectAllChk)

        # Fetched-playlist table
        self.fetchTable = QTableView()
        self.fetchTable.setModel(self.fetchModel)
        
        # allow clicking checkbox cells to toggle selection
        self.fetchTable.setEditTriggers(
            QTableView.EditTrigger.SelectedClicked
            | QTableView.EditTrigger.DoubleClicked
            | QTableView.EditTrigger.CurrentChanged
        )
        # ensure our click handler toggles the model
        self.fetchTable.clicked.connect(self.on_fetch_table_clicked)

        # Delegate for per-row format dropdown in column 3
        self.fetchTable.setItemDelegateForColumn(3, FormatDelegate(self.fetchTable))

        # Dynamic column resizing:
        #   - Col 0 (Select) and Col 1 (No) stay interactive
        #   - Col 2 (Description) stretches to fill extra space
        #   - Col 3 (Format) stays interactive
        hdr = self.fetchTable.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        ml.addWidget(self.fetchTable)

        # Save-location + Global Format + Download/Cancel buttons
        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Save Location:"))
        self.saveEdit    = QLineEdit(self.config.default_save_dir)
        self.browseBtn   = QPushButton("Browse")
    

        # Global Format dropdown moved here, styled green
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["1080p", "720p", "480p", "360p"])
        self.formatCombo.setStyleSheet("background-color: #c8e6c9;")

        hl2.addWidget(self.saveEdit)
        hl2.addWidget(self.browseBtn)
        hl2.addWidget(QLabel("Global Format:"))
        hl2.addWidget(self.formatCombo)

        self.downloadBtn = QPushButton("Download")
        self.cancelBtn   = QPushButton("Cancel")
        hl2.addWidget(self.downloadBtn)
        hl2.addWidget(self.cancelBtn)
        ml.addLayout(hl2)

        # Download status table
        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        # hide the Format column (index 2)
        self.downloadTable.hideColumn(2)
        # dynamic resizing: let Description (col 1) & Progress (col 3) stretch
        dl_hdr = self.downloadTable.horizontalHeader()
        dl_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Video No
        dl_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)      # Description
        dl_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)        # Format (hidden)
        dl_hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)      # Progress
        dl_hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Status
        ml.addWidget(self.downloadTable)

        self.tabs.addTab(tab_main, "QuickYTDL")

        # --- Complete Log tab ---
        tab_log = QWidget()
        ll = QVBoxLayout(tab_log)
        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        ll.addWidget(self.logView)
        self.tabs.addTab(tab_log, "Complete Log")

        # --- Options tab ---
        tab_opt = QWidget()
        ol = QVBoxLayout(tab_opt)
        self.autoShutdownChk = QCheckBox("Auto shutdown when complete")
        ol.addWidget(self.autoShutdownChk)

        hl3 = QHBoxLayout()
        hl3.addWidget(QLabel("Default Save Location:"))
        self.defSaveEdit  = QLineEdit(self.config.default_save_dir)
        self.defBrowseBtn = QPushButton("Browse")
        hl3.addWidget(self.defSaveEdit)
        hl3.addWidget(self.defBrowseBtn)
        ol.addLayout(hl3)

        self.tabs.addTab(tab_opt, "Options")

    def _connect_signals(self):
        # Fetch button
        self.fetchBtn.clicked.connect(self.on_fetch_clicked)
        # Select All toggle
        self.selectAllChk.stateChanged.connect(self.on_select_all)
        # Browse buttons
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)
        # Download / Cancel
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)
        # Auto-shutdown option
        self.autoShutdownChk.stateChanged.connect(self.on_auto_shutdown_changed)
        # Download progress & completion
        self.manager.progress.connect(self.on_download_progress)
        self.manager.finished.connect(self.on_download_finished)
        # fetcher logs come via the worker; manager logs go directly
        self.manager.log.connect(self.logView.append)
        # Show download progress in log
        self.manager.progress.connect(
            lambda idx, pct, st: self.logView.append(f"[{idx+1}] {st} {int(pct)}%")
        )
        # also listen for download progress logs
        self.manager.progress.connect(
            lambda idx, pct, st: self.logView.append(f"[{idx+1}] {st} {int(pct)}%")
        )   

    def _prompt_for_default_folder(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Cannot Create Default Folder")
        msg.setText(f"Unable to create:\n{self.config.default_save_dir}")
        msg.exec()
        fallback = QFileDialog.getExistingDirectory(
            self, "Select Default Save Directory", os.path.expanduser("~")
        )
        if fallback:
            self.config.default_save_dir = fallback
            ensure_directory(fallback)
            self.config.save()


    @pyqtSlot()
    def on_fetch_clicked(self):
        # If a fetch is already running, cancel it and clear out old rows
        if self._fetch_thread:
            self._cleanup_fetch_thread()
        self.fetchModel.set_items([])
        self.selectAllChk.setChecked(False)
        self.logView.clear()

        # Grab the URL
        url = self.urlEdit.text().strip()
        if not url:
            return

        # Disable Fetch until done
        self.fetchBtn.setEnabled(False)

        # Create and start a fresh fetch worker/thread
        self._fetch_thread = QThread(self)
        self._fetch_worker = FetchWorker(self.fetcher)
        self._fetch_worker.moveToThread(self._fetch_thread)

        # Hook up signals
        self._fetch_worker.finished.connect(self._handle_fetch_done)
        self._fetch_worker.error.connect(self._handle_fetch_error)
        self._fetch_worker.log.connect(self.logView.append)
        self._fetch_thread.finished.connect(self._cleanup_fetch_thread)

        # Kick off the thread
        self._fetch_thread.start()
        self._fetch_worker.fetch_request.emit(url)
        # Default to all selected on new fetch
        self.selectAllChk.setChecked(True)

    @pyqtSlot(list)
    def _handle_fetch_done(self, items: list):
        self.fetchBtn.setEnabled(True)
        self.fetchModel.set_items(items)

        # Apply global format as default selection
        fmt = self.formatCombo.currentText()
        for it in items:
            it.selected = True
            if fmt in it.available_formats:
                it.selected_format = fmt

        #  ── color-code the Global Format combo: green if supported by EVERY video
        common = set.intersection(*(set(it.available_formats) for it in items))
        combo_model = self.formatCombo.model()
        for idx in range(self.formatCombo.count()):
            fmt = self.formatCombo.itemText(idx)
            color = Qt.GlobalColor.green if fmt in common else Qt.GlobalColor.red
            combo_model.setData(combo_model.index(idx, 0),
                                color,
                                Qt.ItemDataRole.ForegroundRole)

        # Notify view to update checkbox & format cells
        if items:
            top = self.fetchModel.index(0, 0)
            bot = self.fetchModel.index(
                self.fetchModel.rowCount() - 1,
                self.fetchModel.columnCount() - 1
            )
            self.fetchModel.dataChanged.emit(
                top, bot,
                [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.EditRole]
            )

    @pyqtSlot(str)
    def _handle_fetch_error(self, message: str):
        self.fetchBtn.setEnabled(True)
        QMessageBox.critical(self, "Fetch Error", message)

    def _cleanup_fetch_thread(self):
        if self._fetch_worker:
            self._fetch_worker.deleteLater()
        if self._fetch_thread:
            self._fetch_thread.quit()
            self._fetch_thread.wait()
            self._fetch_thread.deleteLater()
        self._fetch_worker = None
        self._fetch_thread = None

    @pyqtSlot()
    def on_browse_save(self):
        d = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.saveEdit.text())
        if d:
            self.saveEdit.setText(d)

    @pyqtSlot()
    def on_browse_default(self):
        d = QFileDialog.getExistingDirectory(self, "Select Default Save Directory", self.defSaveEdit.text())
        if d:
            self.defSaveEdit.setText(d)
            self.config.default_save_dir = d
            ensure_directory(d)
            self.config.save()

    @pyqtSlot(int)
    def on_auto_shutdown_changed(self, state):
        self.config.auto_shutdown = (state == Qt.CheckState.Checked)
        self.config.save()

    @pyqtSlot()
    def on_download_clicked(self):
        # Lock UI controls during download
        self.fetchBtn.setEnabled(False)
        self.urlEdit.setEnabled(False)
        self.browseBtn.setEnabled(False)
        self.selectAllChk.setEnabled(False)
        self.downloadBtn.setEnabled(False)

        sel = self.fetchModel.get_selected_items()
        if not sel:
            return
        save_dir = self.saveEdit.text().strip() or self.config.default_save_dir
        ensure_directory(save_dir)
        self.downloadModel.set_items(sel)
        self.manager.start_downloads(sel, save_dir) 

    @pyqtSlot()
    def on_cancel_clicked(self):
        # cancel all running downloads...
        self.manager.cancel_all()
        # and immediately re-enable the UI
        self.fetchBtn.setEnabled(True)
        self.urlEdit.setEnabled(True)
        self.browseBtn.setEnabled(True)
        self.selectAllChk.setEnabled(True)
        self.downloadBtn.setEnabled(True)

    @pyqtSlot(int, float, str)
    def on_download_progress(self, idx: int, pct: float, status: str):
        self.downloadModel.update_progress(idx, pct, status)

    @pyqtSlot(int, str)
    def on_download_finished(self, idx: int, status: str):
        self.downloadModel.update_status(idx, status)
        statuses = self.downloadModel.get_statuses()
        # Once everything’s done, re-enable the UI
        if all(s in ("Completed", "Skipped") for s in statuses):
            self.fetchBtn.setEnabled(True)
            self.urlEdit.setEnabled(True)
            self.browseBtn.setEnabled(True)
            self.selectAllChk.setEnabled(True)
            self.downloadBtn.setEnabled(True)
            if self.autoShutdownChk.isChecked():
                if os.name == "nt":
                    os.system("shutdown /s /t 60")
                else:
                    os.system("shutdown now")
    
    @pyqtSlot(int)
    def on_select_all(self, state: int):
        """
        Toggle every row’s checkbox in the fetch table when the
        'Select All' checkbox is changed.
        """
        checked = (state == Qt.CheckState.Checked)
        # Flip each VideoItem.selected
        for item in self.fetchModel._items:
            item.selected = checked
        # Notify the table view to redraw the checkbox column
        row_count = self.fetchModel.rowCount()
        if row_count:
            top = self.fetchModel.index(0, 0)
            bot = self.fetchModel.index(row_count - 1, 0)
            self.fetchModel.dataChanged.emit(
                top, bot, [Qt.ItemDataRole.CheckStateRole]
            )

    @pyqtSlot("QModelIndex")
    def on_fetch_table_clicked(self, index):
        # if user clicked the checkbox column, toggle manually
        if index.column() == 0:
            current = self.fetchModel._items[index.row()].selected
            new_state = Qt.CheckState.Checked if not current else Qt.CheckState.Unchecked
            self.fetchModel.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
