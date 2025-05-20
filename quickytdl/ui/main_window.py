# quickytdl/ui/main_window.py

import os
import re

from PyQt6.QtWidgets import (
    QProgressBar,QMainWindow, QWidget, QLineEdit, QComboBox, QPushButton,
    QTableView, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QLabel, QMessageBox,
    QStyledItemDelegate, QHeaderView,
    QStyleOptionProgressBar, QStyle, QApplication,
    QStyleOptionButton, QStyleOptionViewItem, QCheckBox,
)
from PyQt6.QtCore import (
    pyqtSlot, Qt, QThread, QObject, pyqtSignal, QRect
)
from PyQt6.QtGui import QPainter, QIcon
from quickytdl.models import PlaylistTableModel, DownloadTableModel
from quickytdl.fetcher import PlaylistFetcher
from quickytdl.manager import DownloadManager
from quickytdl.config import ConfigManager
from quickytdl.utils import ensure_directory


class FormatDelegate(QStyledItemDelegate):
    """Delegate to render a QComboBox in the 'Format' column per row."""
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
    """Renders a progress bar with centered percentage text (ignores any trailing speed text)."""
    def paint(self, painter: QPainter, option, index):
        # 1) Grab the display string from the model, e.g. "42% 1.2MiB/s"
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""
        # 2) Extract the leading integer percentage
        try:
            token = raw.split()[0]               # first token, e.g. "42%"
            if token.endswith('%'):
                token = token[:-1]
            value = int(token)
        except Exception:
            value = 0

        # 3) Configure the progress‐bar style option
        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = value
        opt.text = f"{value}%"
        opt.textVisible = True
        opt.textAlignment = Qt.AlignmentFlag.AlignCenter

        # 4) Draw it
        painter.save()
        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ProgressBar, opt, painter
        )
        painter.restore()


class CheckBoxHeader(QHeaderView):
    """Draws a checkbox in column-0’s header and emits toggled(bool)."""
    toggled = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self._isChecked = False

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex == 0:
            opt = QStyleOptionButton()
            size = self.style().sizeFromContents(
                QStyle.ContentsType.CT_CheckBox, opt, rect.size(), None
            )
            opt.rect = QRect(
                rect.x() + 5,
                rect.y() + (rect.height() - size.height()) // 2,
                size.width(), size.height()
            )
            opt.state = (
                QStyle.StateFlag.State_Enabled
                | (QStyle.StateFlag.State_On if self._isChecked
                   else QStyle.StateFlag.State_Off)
            )
            self.style().drawControl(
               QStyle.ControlElement.CE_CheckBox, opt, painter
           )

    def mousePressEvent(self, event):
        col = self.logicalIndexAt(event.pos())
        if col == 0:
            self._isChecked = not self._isChecked
            self.toggled.emit(self._isChecked)
            self.updateSection(0)
        else:
            super().mousePressEvent(event)


class FetchWorker(QObject):
    """Offloads playlist metadata fetching into its own thread."""
    fetch_request = pyqtSignal(str)
    finished      = pyqtSignal(list)
    error         = pyqtSignal(str)
    log           = pyqtSignal(str)

    def __init__(self, fetcher: PlaylistFetcher):
        super().__init__()
        self.fetcher = fetcher
        self.fetch_request.connect(
            self._on_fetch, Qt.ConnectionType.QueuedConnection
        )
        self.fetcher.log.connect(self.log)

    @pyqtSlot(str)
    def _on_fetch(self, url: str):
        try:
            items = self.fetcher.fetch_playlist(url)
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # once fetch is done (or errors), exit this thread's event loop
            QThread.currentThread().quit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ── set application icon ───────────────────────────────────────
        # resource path from the compiled resources_rc.py
        #self.setWindowIcon(QIcon(":/QuickYTDL.ico"))
        self.setWindowTitle("QuickYTDL")
        self.resize(1000, 700)
        #self.statusBar().showMessage("Ready")
       # add progress bar to status bar
        self.sb_progress = QProgressBar()
        self.sb_progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.sb_progress)

        # ── Load settings ─────────────────────────────────────────
        self.config = ConfigManager()
        self.config.load()
        if not os.path.isdir(self.config.default_save_dir):
            self._prompt_for_default_folder()

        # ── Core components ───────────────────────────────────────
        self.fetcher = PlaylistFetcher()
        self.manager = DownloadManager()

        # ── Data models ───────────────────────────────────────────
        self.fetchModel    = PlaylistTableModel([])
        self.downloadModel = DownloadTableModel([])

        # ── Build UI + hook signals ───────────────────────────────
        self._build_ui()
        self._connect_signals()

        # restore auto-shutdown checkbox
        self.autoShutdownChk.setChecked(self.config.auto_shutdown)

        # placeholders for fetch thread/worker
        self._fetch_thread = None
        self._fetch_worker = None

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # --- Main Download Tab ---
        tab_main = QWidget()
        ml = QVBoxLayout(tab_main)

        # URL + Fetch button
        h1 = QHBoxLayout()
        self.urlEdit  = QLineEdit()
        self.urlEdit.setPlaceholderText("Playlist URL")
        self.fetchBtn = QPushButton("Fetch")
        h1.addWidget(self.urlEdit)
        h1.addWidget(self.fetchBtn)
        ml.addLayout(h1)

        # Fetched-playlist table
        self.fetchTable = QTableView()
        self.fetchTable.setModel(self.fetchModel)

        # ── install a single header‐checkbox in column 0 ─────────────────
        header = CheckBoxHeader(Qt.Orientation.Horizontal, self.fetchTable)
        self.fetchTable.setHorizontalHeader(header)
        self.fetchHeader = header  # keep a reference so we can reset it later
        header.toggled.connect(self.on_select_all)  # emit True/False on clicks

        # disable built-in edits; we handle selection clicks manually
        self.fetchTable.setEditTriggers(
            QTableView.EditTrigger.NoEditTriggers
        )
        self.fetchTable.clicked.connect(self.on_fetch_table_clicked)

        # per-row Format dropdown
        self.fetchTable.setItemDelegateForColumn(
            3, FormatDelegate(self.fetchTable)
        )

        # dynamic column widths
        hdr = header
        hdr.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        hdr.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        hdr.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        hdr.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive
        )
        ml.addWidget(self.fetchTable)

        # Save-location + Global Format + controls
        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Save Location:"))
        self.saveEdit  = QLineEdit(self.config.default_save_dir)
        self.browseBtn = QPushButton("Browse")
        hl2.addWidget(self.saveEdit)
        hl2.addWidget(self.browseBtn)

        self.formatCombo = QComboBox()
        self.formatCombo.addItems([
            "1080p", "720p", "480p", "360p", "mp3"  # ✅ added mp3
        ])
        #self.formatCombo.setStyleSheet("background-color: #c8e6c9;")

        hl2.addWidget(QLabel("Global Format:"))
        hl2.addWidget(self.formatCombo)
        hl2.addWidget(QLabel("Global Format:"))
        hl2.addWidget(self.formatCombo)
        # ── sample-rate selector (MP3 only) ──────────────────────────────────
        hl2.addWidget(QLabel("SR (Hz):"))
        self.srCombo = QComboBox()
        self.srCombo.addItems(["44100", "48000"])
        self.srCombo.setEnabled(False)
        hl2.addWidget(self.srCombo)
        
        self.downloadBtn = QPushButton("Download")
        self.cancelBtn   = QPushButton("Cancel")
        hl2.addWidget(self.downloadBtn)
        hl2.addWidget(self.cancelBtn)
        ml.addLayout(hl2)

        # Download status table
        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        self.downloadTable.hideColumn(2)  # hide per-row format

        # progress‐bar delegate
        self.downloadTable.setItemDelegateForColumn(
            3, ProgressBarDelegate(self.downloadTable)
        )

        dl_hdr = self.downloadTable.horizontalHeader()
        dl_hdr.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        dl_hdr.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        dl_hdr.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        dl_hdr.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        dl_hdr.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Interactive
        )
        ml.addWidget(self.downloadTable)

        self.tabs.addTab(tab_main, "QuickYTDL")

        # --- Complete Log Tab ---
        tab_log = QWidget()
        ll = QVBoxLayout(tab_log)
        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        ll.addWidget(self.logView)
        self.tabs.addTab(tab_log, "Complete Log")

        # --- Options Tab ---
        tab_opt = QWidget()
        ol = QVBoxLayout(tab_opt)
        self.autoShutdownChk = QCheckBox("Auto shutdown when complete")
        ol.addWidget(self.autoShutdownChk)

        hl3 = QHBoxLayout()
        hl3.addWidget(QLabel("Default Save Location:"))
        self.defSaveEdit  = QLineEdit(
            self.config.default_save_dir
        )
        self.defBrowseBtn = QPushButton("Browse")
        hl3.addWidget(self.defSaveEdit)
        hl3.addWidget(self.defBrowseBtn)
        ol.addLayout(hl3)
        self.tabs.addTab(tab_opt, "Options")

    def _connect_signals(self):
        # Fetch
        #self.fetchBtn.clicked.connect(self.on_fetch_clicked)
        # Fetch button + route its logs
        self.fetchBtn.clicked.connect(self.on_fetch_clicked)
        # send every fetcher.log into the text log AND status‐bar handler
        self.fetcher.log.connect(self.logView.append)
        self.fetcher.log.connect(self._on_log_message)

        # Browse
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)

        # Download / Cancel
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        # enable SR dropdown only when MP3 is chosen
        self.formatCombo.currentTextChanged.connect(
            lambda fmt: self.srCombo.setEnabled(fmt == "mp3")
        )
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)

        # Auto-shutdown
        self.autoShutdownChk.stateChanged.connect(
            self.on_auto_shutdown_changed
        )
        # now also include speed & eta
        # Download progress & completion (5-arg progress hook: idx, pct, status, speed, eta)
        # this slot will also update the status bar with speed & ETA
        self.manager.progress.connect(self.on_download_progress)
        self.manager.finished.connect(self.on_download_finished)
        self.manager.log.connect(self.logView.append)
        # route log events into the status bar for highlights
        self.manager.log.connect(self._on_log_message)

        # connect download and log signals

    def _prompt_for_default_folder(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Cannot Create Default Folder")
        msg.setText(
            f"Unable to create:\n{self.config.default_save_dir}"
        )
        msg.exec()
        fallback = QFileDialog.getExistingDirectory(
            self, "Select Default Save Directory",
            os.path.expanduser("~")
        )
        if fallback:
            self.config.default_save_dir = fallback
            ensure_directory(fallback)
            self.config.save()

    @pyqtSlot()
    def on_fetch_clicked(self):
        # If a fetch is already running, cancel it & clear table/log
        if self._fetch_thread:
            self._cleanup_fetch_thread()
        self.fetchModel.set_items([])
        self.logView.clear()

        url = self.urlEdit.text().strip()
        if not url:
            return

        self.fetchBtn.setEnabled(False)

        # start fetch worker
        self._fetch_thread = QThread(self)
        self._fetch_worker = FetchWorker(self.fetcher)
        self._fetch_worker.moveToThread(self._fetch_thread)

        # signals
        self._fetch_worker.finished.connect(self._handle_fetch_done)
        self._fetch_worker.error.connect(self._handle_fetch_error)
        self._fetch_worker.log.connect(self.logView.append)
        self._fetch_thread.finished.connect(self._cleanup_fetch_thread)

        # fire
        self._fetch_thread.start()
        self._fetch_worker.fetch_request.emit(url)

        # default to all selected: set header state + select all rows
        self.fetchHeader._isChecked = True
        self.fetchHeader.updateSection(0)
        self.on_select_all(True)

    @pyqtSlot(list)
    def _handle_fetch_done(self, items: list):
        self.fetchBtn.setEnabled(True)
        self.fetchModel.set_items(items)

        # automatically pick subfolder named after playlist
        # under user’s default save dir
        title = self.fetcher.last_playlist_title or ""
        base = os.path.join(self.config.default_save_dir, title)
        ensure_directory(base)
        self.saveEdit.setText(base)

        # Apply global format to each item
        fmt = self.formatCombo.currentText()
        for it in items:
            it.selected = True
            if fmt in it.available_formats:
                it.selected_format = fmt

        #  ── color-code the Global Format combo: green if supported by EVERY video
        # (drive intersection off of the first set to avoid unbound method issues)
        if items:
            common = set(items[0].available_formats)
            for it in items[1:]:
                common &= set(it.available_formats)
        else:
            common = set()
        combo_model = self.formatCombo.model()
        for idx in range(self.formatCombo.count()):
            f = self.formatCombo.itemText(idx)
            clr = Qt.GlobalColor.green if f in common else Qt.GlobalColor.red
            combo_model.setData(combo_model.index(idx, 0),
                                clr,
                                Qt.ItemDataRole.ForegroundRole)

        # refresh table view
        if items:
            top = self.fetchModel.index(0, 0)
            bot = self.fetchModel.index(
                self.fetchModel.rowCount()-1,
                self.fetchModel.columnCount()-1
            )
            self.fetchModel.dataChanged.emit(
                top, bot,
                [Qt.ItemDataRole.CheckStateRole,
                 Qt.ItemDataRole.EditRole]
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
        d = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.saveEdit.text()
        )
        if d:
            self.saveEdit.setText(d)

    @pyqtSlot()
    def on_browse_default(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Default Save Directory", self.defSaveEdit.text()
        )
        if d:
            self.defSaveEdit.setText(d)
            self.config.default_save_dir = d
            ensure_directory(d)
            self.config.save()

    @pyqtSlot(int)
    def on_auto_shutdown_changed(self, state):
        self.config.auto_shutdown = (
            state == Qt.CheckState.Checked
        )
        self.config.save()

    @pyqtSlot()
    def on_download_clicked(self):
        # lock out UI during download
        self.fetchBtn.setEnabled(False)
        self.urlEdit.setEnabled(False)
        self.browseBtn.setEnabled(False)
        self.downloadBtn.setEnabled(False)

        sel = self.fetchModel.get_selected_items()
        if not sel:
            return

        # override per-item format from global dropdown and attach sample rate
        fmt = self.formatCombo.currentText()
        sr = int(self.srCombo.currentText()) if fmt == "mp3" else None
        for it in sel:
            it.selected_format = fmt
            setattr(it, 'sample_rate', sr)

        save_dir = (
            self.saveEdit.text().strip()
            or self.config.default_save_dir
        )
        #ensure_directory(save_dir)
        self.downloadModel.set_items(sel)
        self.manager.start_downloads(sel, save_dir)
        # make sure the status-bar progress is hidden once we hit download
        #self.sb_progress.setVisible(False)
        #ensure_directory(save_dir)

    @pyqtSlot()
    def on_cancel_clicked(self):
        # 1) Stop any downloads in progress and clear that table
        self.manager.cancel_all()
        self.downloadModel.set_items([])

        # 2) Prevent any late fetch callbacks from touching our UI
        if self._fetch_worker:
            try:
                self._fetch_worker.finished.disconnect(self._handle_fetch_done)
                self._fetch_worker.error.disconnect(self._handle_fetch_error)
                self._fetch_worker.log.disconnect(self.logView.append)
            except Exception:
                pass

        # 3) Clear the fetch table entirely
        self.fetchModel.set_items([])

        # 4) Reset the header‐checkbox back to “unchecked”
        # reset header checkbox so future toggles always work
        self.fetchHeader._isChecked = False
        self.fetchHeader.updateSection(0)

        # 5) Unblock every UI control so the user can start fresh
        self.fetchBtn.setEnabled(True)
        self.urlEdit.setEnabled(True)
        self.browseBtn.setEnabled(True)
        self.downloadBtn.setEnabled(True)

    @pyqtSlot(int, float, str, str, str)
    def on_download_progress(self,
                             idx: int,
                             pct: float,
                             status: str,
                             speed: str,
                             eta: str):
        """
        DownloadWorker.progress(index, percent, status, speed, eta).
        Updates the per‐row progress bar/status and shows speed & ETA
        in the main window's status bar.
        """
    # update the table cell (percent + optional “Merging” or “Downloading” text)
        self.downloadModel.update_progress(idx, pct, status)
        # guard against any out-of-bounds idx
        if 0 <= idx < len(self.downloadModel._items):
            # store speed & ETA on that item (if you need it later)
            item = self.downloadModel._items[idx]
            item.speed = speed
            item.eta   = eta

        self.statusBar().showMessage(
             f"Video {idx+1} | Progress: {pct:4.0f}% | Speed: {speed:<8} | ETA: {eta}"
         )
        # build a fixed-width, column-aligned message
        msg = (
            f"Video {idx+1:>3} | "
            f"Progress: {pct:>3.0f}% | "
            f"Speed: {speed:>10} | "
            f"ETA: {eta:>5}"
        )
        self.statusBar().showMessage(msg)
        # drive the determinate progress bar when visible
        if self.sb_progress.isVisible() and self.sb_progress.maximum() == 100:
            self.sb_progress.setValue(int(pct))

    @pyqtSlot(int, float, str, str, str)
    def _show_speed_in_statusbar(self, idx: int, pct: float, status: str, speed: str, eta: str):
        """
        Show a summary of the current download speed & ETA
        in the window’s status bar.
        """
        self.statusBar().showMessage(f"{pct:4.1f}% • {speed} • ETA {eta}")

    @pyqtSlot(int, str)
    def on_download_finished(self, idx: int, status: str):
        self.downloadModel.update_status(idx, status)
        statuses = self.downloadModel.get_statuses()
        if all(s in ("Completed", "Skipped") for s in statuses):
            # re-enable UI
            self.fetchBtn.setEnabled(True)
            self.urlEdit.setEnabled(True)
            self.browseBtn.setEnabled(True)
            self.downloadBtn.setEnabled(True)
            # clear the status‐bar once done
            self.statusBar().clearMessage()
            # hide progress bar and show finished message
            self.sb_progress.setVisible(False)
            self.statusBar().showMessage("All downloads completed.")
            if self.autoShutdownChk.isChecked():
                if os.name == "nt":
                    os.system("shutdown /s /t 60")
                else:
                    os.system("shutdown now")

    @pyqtSlot(bool)
    def on_select_all(self, checked: bool):
        """Header checkbox toggled: select/deselect every row."""
        state = (
            Qt.CheckState.Checked
            if checked else Qt.CheckState.Unchecked
        )
        for row in range(self.fetchModel.rowCount()):
            idx = self.fetchModel.index(row, 0)
            self.fetchModel.setData(
                idx, state,
                Qt.ItemDataRole.CheckStateRole
            )

    @pyqtSlot("QModelIndex")
    def on_fetch_table_clicked(self, index):
        """Toggle a single row when its checkbox cell is clicked."""
        if index.column() == 0:
            curr = self.fetchModel._items[index.row()].selected
            new_st = (
                Qt.CheckState.Checked
                if not curr else Qt.CheckState.Unchecked
            )
            self.fetchModel.setData(
                index, new_st,
                Qt.ItemDataRole.CheckStateRole
            )

    @pyqtSlot(int, float, str, str, str)
    def _show_speed_in_statusbar(self, idx, pct, status, speed, eta):
        """
        Display a summary in the status bar like:
           "42.3% at 120.5KiB/s  ETA 02:15"
        """
        # you could also show total size if you had stored it on each item
        self.statusBar().showMessage(
            f"{pct:4.1f}% at {speed}  ETA {eta}"
        )
    @pyqtSlot(str)
    def _on_log_message(self, message: str):
        """
        Highlight key operations in the status bar and control the sb_progress widget.
        """
        # normalize the incoming text
        text = message.strip()

        # 1) Show key emoji messages immediately
        if text.startswith(("🔍", "🔎", "✅", "🚀", "⏬")):
            self.statusBar().showMessage(text)

        # 2) Start of metadata fetch -> indeterminate progress
        if text.startswith("🔍"):
            self.sb_progress.setVisible(True)
            self.sb_progress.setRange(0, 0)
            return

        # 3) Playlist metadata entries progress: "[i/n]" -> determinate
        m = re.search(r"\[(\d+)/(\d+)\]", text)
        if m:
            current, total = map(int, m.groups())
            pct = int(current / total * 100)
            self.sb_progress.setVisible(True)
            self.sb_progress.setRange(0, 100)
            self.sb_progress.setValue(pct)
            return

        # 4) Total count found -> hide indeterminate bar
        if text.startswith("🔎"):
            self.sb_progress.setVisible(False)
            return

        # 5) Metadata extraction completed -> hide bar
        if text.startswith("✅") and "metadata" in text.lower():
            self.sb_progress.setVisible(False)
            return
        # 6) Download phase start -> hide status-bar bar entirely
        if text.startswith("🚀"):
            self.sb_progress.setVisible(False)
            return
