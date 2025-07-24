# quickytdl/ui/main_window.py

import os
import re
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStyledItemDelegate, QStyle, QStyleOptionButton,
    QStyleOptionProgressBar, QTextEdit, QVBoxLayout, QWidget, QMainWindow, 
    QTableView, QGroupBox
)
from PyQt6.QtCore import (
    Qt, QThread, QUrl, QRect, pyqtSlot, pyqtSignal, QObject
)
from PyQt6.QtGui import QDesktopServices, QPainter

from quickytdl.models import PlaylistTableModel, DownloadTableModel
from quickytdl.fetcher import PlaylistFetcher
from quickytdl.manager import DownloadManager
from quickytdl.config import ConfigManager
from quickytdl.utils import ensure_directory

class FormatDelegate(QStyledItemDelegate):
    """Render a per-row QComboBox for selecting formats."""
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
    """Render a cleaner text-based progress bar with ▓░ blocks, % center, and right-aligned speed/ETA."""
    def paint(self, painter: QPainter, option, index):
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""

        # Parse expected format: "45% │ 3.2MB/s │ ETA 00:30"
        parts = raw.split("│")
        percent_str = parts[0].strip() if len(parts) > 0 else "0%"
        speed = parts[1].strip() if len(parts) > 1 else ""
        eta = parts[2].strip() if len(parts) > 2 else ""

        try:
            percent = int(percent_str.rstrip('%'))
        except Exception:
            percent = 0

        # Bar setup
        total_blocks = 20
        filled = int((percent / 100) * total_blocks)
        empty = total_blocks - filled
        bar = f"{'▓' * filled}{'░' * empty}"

        # Compose full line
        display_text = f"{bar} {percent:>3}%   {speed}   {eta}"

        # Draw nicely aligned
        painter.save()
        painter.setFont(option.font)

        # Draw gray background for visual contrast (optional)
        painter.fillRect(option.rect, option.palette.alternateBase())

        # Draw the text
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, display_text)
        painter.restore()



class CheckBoxHeader(QHeaderView):
    """
    Draw a clickable checkbox in column-0’s header.
    Emits toggled(bool) when clicked.
    """
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
            opt.state = QStyle.StateFlag.State_Enabled
            opt.state |= (
                QStyle.StateFlag.State_On
                if self._isChecked else QStyle.StateFlag.State_Off
            )
            self.style().drawControl(
                QStyle.ControlElement.CE_CheckBox, opt, painter
            )

    def mousePressEvent(self, event):
        if self.logicalIndexAt(event.pos()) == 0:
            self._isChecked = not self._isChecked
            self.toggled.emit(self._isChecked)
            self.updateSection(0)
        else:
            super().mousePressEvent(event)


class FetchWorker(QObject):
    """
    Worker to fetch playlist metadata in its own thread.
    Emits:
      - finished(list_of_items)
      - error(str)
      - log(str)
    """
    fetch_request = pyqtSignal(str)
    finished      = pyqtSignal(list)
    error         = pyqtSignal(str)
    log           = pyqtSignal(str)

    def __init__(self, fetcher: PlaylistFetcher):
        super().__init__()
        self.fetcher = fetcher
        self.fetch_request.connect(self._on_fetch, Qt.ConnectionType.QueuedConnection)
        self.fetcher.log.connect(self.log)

    @pyqtSlot(str)
    def _on_fetch(self, url: str):
        """Triggered when fetch_request is emitted."""
        try:
            items = self.fetcher.fetch_playlist(url)
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            QThread.currentThread().quit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickYTDL")
        self.resize(1200, 800)

        self.sb_progress = QProgressBar()
        self.sb_progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.sb_progress)

        self.openFolderBtn = QPushButton("Open Folder")
        self.openFolderBtn.setVisible(False)
        self.openFolderBtn.clicked.connect(self._open_download_dir)
        self.statusBar().addPermanentWidget(self.openFolderBtn)

        

        self.config = ConfigManager()
        self.config.load()
        if not os.path.isdir(self.config.default_save_dir):
            self._prompt_for_default_folder()

        self.fetcher = PlaylistFetcher()
        self.manager = DownloadManager()

        self.fetchModel = PlaylistTableModel([])
        self.downloadModel = DownloadTableModel([])

        self._build_ui()
        self._connect_signals()

        self.autoShutdownChk.setChecked(self.config.auto_shutdown)
        self.fetchBtn.setEnabled(False)
        self.downloadBtn.setEnabled(False)
        self.urlEdit.textChanged.connect(self._update_fetch_button_state)
        self.fetchModel.dataChanged.connect(lambda *_: self._update_download_button_state())
        self.fetchHeader.toggled.connect(lambda _: self._update_download_button_state())

        self._fetch_thread = None
        self._fetch_worker = None

    def _toggle_log_view(self):
        visible = self.logViewContainer.isVisible()
        self.logViewContainer.setVisible(not visible)
        self.logToggleBtn.setChecked(not visible)

    def _toggle_options_view(self):
        visible = self.optionsContainer.isVisible()
        self.optionsContainer.setVisible(not visible)
        self.optToggleBtn.setChecked(not visible)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        self.urlEdit = QLineEdit()
        self.urlEdit.setPlaceholderText("Playlist URL")
        self.fetchBtn = QPushButton("Fetch")
        h1 = QHBoxLayout()
        h1.addWidget(self.urlEdit)
        h1.addWidget(self.fetchBtn)
        vbox.addLayout(h1)

        self.fetchTable = QTableView()
        self.fetchTable.setModel(self.fetchModel)
        header = CheckBoxHeader(Qt.Orientation.Horizontal, self.fetchTable)
        self.fetchTable.setHorizontalHeader(header)
        self.fetchHeader = header
        header.toggled.connect(self.on_select_all)
        self.fetchTable.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.fetchTable.clicked.connect(self.on_fetch_table_clicked)
        self.fetchTable.setItemDelegateForColumn(3, FormatDelegate(self.fetchTable))
        fetch_hdr = self.fetchTable.horizontalHeader()
        for col, mode in enumerate([
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Interactive
        ]):
            fetch_hdr.setSectionResizeMode(col, mode)
        self.fetch_group = QGroupBox("Fetched Playlist")
        fetch_layout = QVBoxLayout(self.fetch_group)
        fetch_layout.addWidget(self.fetchTable)
        vbox.addWidget(self.fetch_group)

        self.saveEdit = QLineEdit(self.config.default_save_dir)
        self.browseBtn = QPushButton("Browse")
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["1080p", "720p", "480p", "360p", "mp3"])
        self.srCombo = QComboBox()
        self.srCombo.addItems(["44100", "48000"])
        self.srCombo.setEnabled(False)
        self.downloadBtn = QPushButton("Download")
        self.cancelBtn = QPushButton("Cancel")

        # Wrap the full control bar in a group box
        self.controlGroup = QGroupBox("Controls")
        control_layout = QHBoxLayout(self.controlGroup)

        self.logToggleBtn = QPushButton("📄")
        self.logToggleBtn.setToolTip("Show/Hide Log")
        self.logToggleBtn.setCheckable(True)
        self.logToggleBtn.setFixedWidth(30)
        self.logToggleBtn.clicked.connect(self._toggle_log_view)
        control_layout.addWidget(self.logToggleBtn)

        self.optToggleBtn = QPushButton("⚙️")
        self.optToggleBtn.setToolTip("Show/Hide Options")
        self.optToggleBtn.setCheckable(True)
        self.optToggleBtn.setFixedWidth(30)
        self.optToggleBtn.clicked.connect(self._toggle_options_view)
        control_layout.addWidget(self.optToggleBtn)

        control_layout.addWidget(QLabel("Save Location: "))
        control_layout.addWidget(self.saveEdit)
        control_layout.addWidget(self.browseBtn)
        control_layout.addWidget(QLabel("Format: "))
        control_layout.addWidget(self.formatCombo)
        control_layout.addWidget(QLabel("SR (Hz): "))
        control_layout.addWidget(self.srCombo)
        control_layout.addWidget(self.downloadBtn)
        control_layout.addWidget(self.cancelBtn)
        vbox.addWidget(self.controlGroup)

        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        self.downloadTable.hideColumn(2)
        self.downloadTable.setItemDelegateForColumn(3, ProgressBarDelegate(self.downloadTable))
        dl_hdr = self.downloadTable.horizontalHeader()
        for col, mode in enumerate([
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Fixed,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Interactive
        ]):
            dl_hdr.setSectionResizeMode(col, mode)
        #vbox.addWidget(self.downloadTable)
        self.download_group = QGroupBox("Download Progress")
        download_layout = QVBoxLayout(self.download_group)
        download_layout.addWidget(self.downloadTable)
        vbox.addWidget(self.download_group)
        self.download_group.setVisible(False)

        self.logViewContainer = QWidget()
        self.logViewContainer.setVisible(False)
        log_layout = QVBoxLayout(self.logViewContainer)
        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        log_layout.addWidget(self.logView)
        vbox.addWidget(self.logViewContainer)

        self.optionsContainer = QWidget()
        self.optionsContainer.setVisible(False)
        opt_layout = QVBoxLayout(self.optionsContainer)
        self.autoShutdownChk = QCheckBox("Auto shutdown when complete")
        opt_layout.addWidget(self.autoShutdownChk)
        hl3 = QHBoxLayout()
        self.defSaveEdit = QLineEdit(self.config.default_save_dir)
        self.defBrowseBtn = QPushButton("Browse")
        hl3.addWidget(QLabel("Default Save Location:"))
        hl3.addWidget(self.defSaveEdit)
        hl3.addWidget(self.defBrowseBtn)
        opt_layout.addLayout(hl3)
        vbox.addWidget(self.optionsContainer)


    def _connect_signals(self):
        """Hook up all button clicks, model signals, and manager events."""
        # Fetch workflow
        self.fetchBtn.clicked.connect(self.on_fetch_clicked)
        self.fetcher.log.connect(self.logView.append)
        self.fetcher.log.connect(self._on_log_message)

        # Browse dialogs
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)

        # Download controls
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)
        self.formatCombo.currentTextChanged.connect(
            lambda fmt: self.srCombo.setEnabled(fmt == "mp3")
        )
        self.manager.progress.connect(self.on_download_progress)
        self.manager.finished.connect(self.on_download_finished)

        # Auto-shutdown option
        self.autoShutdownChk.stateChanged.connect(self.on_auto_shutdown_changed)

    def _prompt_for_default_folder(self):
        """Alert + ask user to select a valid default save directory."""
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

    def _update_fetch_button_state(self):
        """Enable Fetch only when URL is non-empty and valid."""
        txt = self.urlEdit.text().strip()
        ok = bool(txt) and QUrl(txt).isValid()
        self.fetchBtn.setEnabled(ok)

    def _update_download_button_state(self):
        """Enable Download when ≥1 playlist item is selected."""
        has_sel = bool(self.fetchModel.get_selected_items())
        self.downloadBtn.setEnabled(has_sel)
    
    def _show_fetch_view(self):
        self.fetch_group.setVisible(True)
        self.download_group.setVisible(False)

    def _show_download_view(self):
        self.fetch_group.setVisible(False)
        self.download_group.setVisible(True)
        

    # ── Slot implementations for fetch/download workflows ───────────────────────────

    @pyqtSlot()
    def on_fetch_clicked(self):
        """Start or restart playlist metadata fetch."""
        if self._fetch_thread:
            self._cleanup_fetch_thread()

        self.fetchModel.set_items([])
        self.logView.clear()

        url = self.urlEdit.text().strip()
        if not url:
            return

        self.fetchBtn.setEnabled(False)

        # Spin up worker thread
        self._fetch_thread = QThread(self)
        self._fetch_worker = FetchWorker(self.fetcher)
        self._fetch_worker.moveToThread(self._fetch_thread)

        # Wire signals
        self._fetch_worker.finished.connect(self._handle_fetch_done)
        self._fetch_worker.error.connect(self._handle_fetch_error)
        #self._fetch_worker.log.connect(self.logView.append)
        self._fetch_thread.finished.connect(self._cleanup_fetch_thread)

        self._fetch_thread.start()
        self._fetch_worker.fetch_request.emit(url)

        # pre-check all rows
        self.fetchHeader._isChecked = True
        self.fetchHeader.updateSection(0)
        self.on_select_all(True)
        self._show_fetch_view()

    @pyqtSlot(list)
    def _handle_fetch_done(self, items: list):
        """Populate table, set save path, and color-code global format."""
        self.fetchBtn.setEnabled(True)
        self.fetchModel.set_items(items)

        title = self.fetcher.last_playlist_title or ""
        base = os.path.join(self.config.default_save_dir, title)
        ensure_directory(base)
        self.saveEdit.setText(base)

        fmt = self.formatCombo.currentText()
        for it in items:
            it.selected = True
            if fmt in it.available_formats:
                it.selected_format = fmt

        # color-code formats: green=available in all, red=not
        if items:
            common = set(items[0].available_formats)
            for it in items[1:]:
                common &= set(it.available_formats)
        else:
            common = set()

        model = self.formatCombo.model()
        for idx in range(self.formatCombo.count()):
            f = self.formatCombo.itemText(idx)
            color = Qt.GlobalColor.green if f in common else Qt.GlobalColor.red
            model.setData(model.index(idx, 0), color, Qt.ItemDataRole.ForegroundRole)

        # trigger a full table refresh
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
        """Tear down fetch thread & worker to avoid leaks."""
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
        """Choose where to save downloads."""
        d = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.saveEdit.text()
        )
        if d:
            self.saveEdit.setText(d)

    @pyqtSlot()
    def on_browse_default(self):
        """Choose default save directory in Options tab."""
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
        """Persist auto-shutdown setting."""
        self.config.auto_shutdown = (state == Qt.CheckState.Checked)
        self.config.save()

    @pyqtSlot()
    def on_download_clicked(self):
        """Begin downloads, lock UI controls."""
        self.downloadBtn.setEnabled(False)
        for w in (
            self.fetchBtn, self.urlEdit, self.saveEdit,
            self.browseBtn, self.formatCombo, self.srCombo
        ):
            w.setEnabled(False)
        self.cancelBtn.setEnabled(True)

        sel = self.fetchModel.get_selected_items()
        if not sel:
            return

        fmt = self.formatCombo.currentText()
        sr = int(self.srCombo.currentText()) if fmt == "mp3" else None
        for it in sel:
            it.selected_format = fmt
            setattr(it, 'sample_rate', sr)

        save_dir = self.saveEdit.text().strip() or self.config.default_save_dir
        self.downloadModel.set_items(sel)
        self.manager.last_download_dir = save_dir
        self.manager.start_downloads(sel, save_dir)
        self._show_download_view()


    @pyqtSlot()
    def on_cancel_clicked(self):
        """Cancel all in-progress downloads and reset UI."""
        self.manager.cancel_all()
        self.downloadModel.set_items([])

        # disconnect any pending fetch callbacks
        if self._fetch_worker:
            try:
                self._fetch_worker.finished.disconnect(self._handle_fetch_done)
                self._fetch_worker.error.disconnect(self._handle_fetch_error)
                self._fetch_worker.log.disconnect(self.logView.append)
            except Exception:
                pass

        # clear playlist table + header state
        self.fetchModel.set_items([])
        self.fetchHeader._isChecked = False
        self.fetchHeader.updateSection(0)

        # restore controls
        for w in (
            self.fetchBtn, self.urlEdit, self.browseBtn,
            self.downloadBtn, self.formatCombo, self.srCombo
        ):
            w.setEnabled(True)
        #self.cancelBtn.setEnabled(False)

        # restore browse button hookup
        try:
            self.browseBtn.clicked.disconnect(self._open_download_dir)
        except TypeError:
            pass
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.browseBtn.setText("Browse")
        self._show_fetch_view()


    @pyqtSlot(int, float, str, str, str)
    def on_download_progress(self, idx: int, pct: float, status: str, speed: str, eta: str):
        """
        Update per-row progress bar & status bar with speed/ETA.
        """
        self.downloadModel.update_progress(idx, pct, status)
        if 0 <= idx < len(self.downloadModel._items):
            item = self.downloadModel._items[idx]
            item.speed = speed
            item.eta = eta

        # fixed-width status message
        msg = (
            f"Video {idx+1:>3} | "
            f"Progress: {pct:>3.0f}% | "
            f"Speed: {speed:<10} | "
            f"ETA: {eta:>5}"
        )
        self.statusBar().showMessage(msg)

        if self.sb_progress.isVisible() and self.sb_progress.maximum() == 100:
            self.sb_progress.setValue(int(pct))

    @pyqtSlot(int, str)
    def on_download_finished(self, idx: int, status: str):
        """Handle one video finishing; when all are done, wrap up."""
        self.downloadModel.update_status(idx, status)
        statuses = self.downloadModel.get_statuses()
        if not all(s in ("Completed", "Skipped") for s in statuses):
            return

        # show final state
        self.sb_progress.setVisible(False)
        self.statusBar().showMessage("All downloads completed.")
        self.browseBtn.setText("Open Directory")
        try:
            self.browseBtn.clicked.disconnect(self.on_browse_save)
        except TypeError:
            pass
        self.browseBtn.clicked.connect(self._open_download_dir)

        for w in (
            self.fetchBtn, self.urlEdit, self.browseBtn,
            self.saveEdit, self.formatCombo, self.srCombo
        ):
            w.setEnabled(True)
        #self.cancelBtn.setEnabled(False)

        if self.autoShutdownChk.isChecked():
            if os.name == "nt":
                os.system("shutdown /s /t 60")
            else:
                os.system("shutdown now")
        self._show_fetch_view()

    @pyqtSlot(bool)
    def on_select_all(self, checked: bool):
        """Toggle all rows’ checkboxes via the header checkbox."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.fetchModel.rowCount()):
            idx = self.fetchModel.index(row, 0)
            self.fetchModel.setData(idx, state, Qt.ItemDataRole.CheckStateRole)

    @pyqtSlot("QModelIndex")
    def on_fetch_table_clicked(self, index):
        """Toggle a single row’s selection when its checkbox cell is clicked."""
        if index.column() != 0:
            return
        item = self.fetchModel._items[index.row()]
        new_state = Qt.CheckState.Checked if not item.selected else Qt.CheckState.Unchecked
        self.fetchModel.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)

    @pyqtSlot(str)
    def _on_log_message(self, message: str):
        """
        Listen to fetcher.log and update status bar / sb_progress
        according to key emojis and metadata progress markers.
        """
        text = message.strip()
        # show key emoji messages
        if text.startswith(("🔍", "🔎", "✅", "🚀", "⏬")):
            self.statusBar().showMessage(text)

        # fetch start → indeterminate
        if text.startswith("🔍"):
            self.sb_progress.setVisible(True)
            self.sb_progress.setRange(0, 0)
            return

        # "[i/n]" progress → determinate
        m = re.search(r"\[(\d+)/(\d+)\]", text)
        if m:
            current, total = map(int, m.groups())
            pct = int(current / total * 100)
            self.sb_progress.setVisible(True)
            self.sb_progress.setRange(0, 100)
            self.sb_progress.setValue(pct)
            return

        # found total count → hide
        if text.startswith("🔎"):
            self.sb_progress.setVisible(False)
            return

        # metadata done → hide
        if text.startswith("✅") and "metadata" in text.lower():
            self.sb_progress.setVisible(False)
            return

        # download phase start → hide
        if text.startswith("🚀"):
            self.sb_progress.setVisible(False)
            return

    @pyqtSlot()
    def _open_download_dir(self):
        """Open the last download folder in the system file manager."""
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(self.manager.last_download_dir)
        )
