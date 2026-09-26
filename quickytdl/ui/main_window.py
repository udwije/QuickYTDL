# quickytdl/ui/main_window.py

import os
import re
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStyledItemDelegate, QStyle, QStyleOptionButton,
    QStyleOptionProgressBar, QTextEdit, QVBoxLayout, QWidget, QMainWindow, 
    QTableView, QGroupBox, QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QThread, QUrl, QRect, pyqtSlot, pyqtSignal, QObject, QEvent, QSize
)
from PyQt6.QtGui import QDesktopServices, QPainter, QIcon, QColor

# Central place to tweak the look of the whole app without hunting through
# every widget constructor. Anything theme-related belongs here.
APP_STYLESHEET = """
QMainWindow {
    background-color: #f5f6fa;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #d8dce6;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #334155;
}
QLabel {
    color: #334155;
}
QLineEdit, QComboBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 8px;
    background: #ffffff;
    selection-background-color: #3b82f6;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}
QLineEdit:disabled, QComboBox:disabled {
    background: #f1f5f9;
    color: #94a3b8;
}
QPushButton {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    background: #ffffff;
    color: #1e293b;
}
QPushButton:hover { background: #f1f5f9; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled {
    background: #f8fafc;
    color: #cbd5e1;
    border-color: #e2e8f0;
}
QPushButton#primaryButton {
    background: #3b82f6;
    border: 1px solid #2563eb;
    color: white;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #2563eb; }
QPushButton#primaryButton:pressed { background: #1d4ed8; }
QPushButton#primaryButton:disabled {
    background: #bfdbfe;
    border-color: #bfdbfe;
    color: #eff6ff;
}
QPushButton#dangerButton {
    background: #ffffff;
    border: 1px solid #ef4444;
    color: #ef4444;
    font-weight: 600;
}
QPushButton#dangerButton:hover { background: #fef2f2; }
QPushButton#dangerButton:disabled {
    border-color: #fecaca;
    color: #fecaca;
}
QTableView {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #eef2f7;
    selection-background-color: #dbeafe;
    selection-color: #1e293b;
    alternate-background-color: #f8fafc;
}
QHeaderView::section {
    background-color: #eef2f7;
    color: #334155;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
}
QTextEdit {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #0f172a;
    color: #d1fae5;
    font-family: Consolas, monospace;
}
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    text-align: center;
    background: #f1f5f9;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
QPushButton#iconToggle {
    padding: 2px;
    font-size: 14px;
}
QPushButton#iconToggle:checked {
    background: #dbeafe;
    border-color: #93c5fd;
}
QLabel#emptyState {
    color: #94a3b8;
    font-size: 13px;
    padding: 24px;
}
"""

from quickytdl.models import PlaylistTableModel, DownloadTableModel
from quickytdl.fetcher import PlaylistFetcher
from quickytdl.manager import DownloadManager
from quickytdl.config import ConfigManager
from quickytdl.utils import ensure_directory

class CancelButtonDelegate(QStyledItemDelegate):
    """
    Renders a small "Cancel" control per download row — but only while
    that row is actually cancelable. Once a row has finished (Completed,
    Canceled, Failed, Skipped) the control disappears instead of sitting
    there as a dead button users can still click.
    """
    clicked = pyqtSignal(int)  # Emits row index

    ACTIVE_STATUSES = {"Queued", "Downloading", "Merging"}

    def _is_active(self, index) -> bool:
        try:
            return index.model()._items[index.row()].status in self.ACTIVE_STATUSES
        except Exception:
            return True

    def paint(self, painter, option, index):
        if not self._is_active(index):
            return
        button = QStyleOptionButton()
        button.rect = option.rect.adjusted(4, 3, -4, -3)
        button.text = "✖ Cancel"
        button.state = QStyle.StateFlag.State_Enabled
        QApplication.style().drawControl(QStyle.ControlElement.CE_PushButton, button, painter)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease and self._is_active(index):
            self.clicked.emit(index.row())
        return True

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
    """
    Paints a clean, rounded, color-coded progress bar instead of ASCII
    blocks. Color reflects the row's actual status (downloading / done /
    canceled / failed) so the state is readable at a glance without
    reading the Status column.
    """
    STATUS_COLORS = {
        "Queued":      QColor("#94a3b8"),  # slate
        "Downloading": QColor("#3b82f6"),  # blue
        "Merging":     QColor("#6366f1"),  # indigo
        "Completed":   QColor("#22c55e"),  # green
        "Canceled":    QColor("#f59e0b"),  # amber
        "Failed":      QColor("#ef4444"),  # red
        "Skipped":     QColor("#a855f7"),  # purple
    }

    def paint(self, painter: QPainter, option, index):
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""
        parts = [p.strip() for p in raw.split("│")]
        percent_str = parts[0] if len(parts) > 0 else "0%"
        extra = " · ".join(p for p in parts[1:] if p)

        try:
            percent = max(0, min(100, int(percent_str.rstrip('%'))))
        except Exception:
            percent = 0

        try:
            status = index.model()._items[index.row()].status
        except Exception:
            status = "Queued"
        color = self.STATUS_COLORS.get(status, QColor("#94a3b8"))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = option.rect.adjusted(4, 5, -4, -5)

        # Track (unfilled background)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e2e8f0"))
        painter.drawRoundedRect(track, 6, 6)

        # Filled portion
        if percent > 0:
            filled = QRect(track)
            filled.setWidth(max(int(track.width() * percent / 100), 10))
            painter.setBrush(color)
            painter.drawRoundedRect(filled, 6, 6)

        # Label: "42%  ·  1.2MiB/s  ·  ETA 00:12"
        label = f"{percent}%" + (f"   {extra}" if extra else "")
        painter.setFont(option.font)
        painter.setPen(QColor("#0f172a"))
        painter.drawText(track, Qt.AlignmentFlag.AlignCenter, label)

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
        self._allFetchedItems = []
        self.setWindowTitle("QuickYTDL")
        self.resize(1200, 800)
        self.setMinimumSize(QSize(820, 560))
        self.setStyleSheet(APP_STYLESHEET)

        self.sb_progress = QProgressBar()
        self.sb_progress.setFixedWidth(160)
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
        self.cancelBtn.setEnabled(False)
        self.urlEdit.textChanged.connect(self._update_fetch_button_state)
        self.fetchModel.dataChanged.connect(lambda *_: self._update_download_button_state())
        self.fetchHeader.toggled.connect(lambda _: self._update_download_button_state())

        self._fetch_thread = None
        self._fetch_worker = None

    def _toggle_log_view(self):
        visible = self.logViewContainer.isVisible()
        self.logViewContainer.setVisible(not visible)
        self.logToggleBtn.setChecked(not visible)
    
    def _append_log(self, msg: str):
        """Append a timestamped message to the log view."""
        from quickytdl.utils import timestamped
        self.logView.append(timestamped(msg))

    def _toggle_options_view(self):
        visible = self.optionsContainer.isVisible()
        self.optionsContainer.setVisible(not visible)
        self.optToggleBtn.setChecked(not visible)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)

        # Wrap Fetch UI in a group box
        self.fetchInputGroup = QGroupBox("Fetch Playlist")
        fetch_input_layout = QHBoxLayout(self.fetchInputGroup)
        self.urlEdit = QLineEdit()
        self.urlEdit.setPlaceholderText("Paste a YouTube video or playlist URL…")
        self.urlEdit.setToolTip("Paste a YouTube video or playlist URL, then press Enter or click Fetch")
        self.urlEdit.setClearButtonEnabled(True)
        self.fetchBtn = QPushButton("🔎  Fetch")
        self.fetchBtn.setObjectName("primaryButton")
        self.fetchBtn.setToolTip("Look up the video(s) at this URL")
        self.fetchBtn.setDefault(True)
        fetch_input_layout.addWidget(self.urlEdit)
        fetch_input_layout.addWidget(self.fetchBtn)
        vbox.addWidget(self.fetchInputGroup)

        # Search option
        """self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search playlist...")
        self.searchEdit.setVisible(True)  # hide until fetched
        self.searchEdit.textChanged.connect(self._filter_playlist)
        vbox.addWidget(self.searchEdit)"""
        self.searchGroup = QGroupBox("Search")
        search_layout = QVBoxLayout(self.searchGroup)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search playlist...")
        self.searchEdit.textChanged.connect(self._filter_playlist)

        search_layout.addWidget(self.searchEdit)
        self.searchGroup.setVisible(False)  # Hide initially
        vbox.addWidget(self.searchGroup)

        # Fetched Table
        self.fetchTable = QTableView()
        self.fetchTable.setModel(self.fetchModel)
        header = CheckBoxHeader(Qt.Orientation.Horizontal, self.fetchTable)
        header.setToolTip("Click to select/deselect all videos")
        self.fetchTable.setHorizontalHeader(header)
        self.fetchHeader = header
        header.toggled.connect(self.on_select_all)
        self.fetchTable.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.fetchTable.clicked.connect(self.on_fetch_table_clicked)
        self.fetchTable.setItemDelegateForColumn(3, FormatDelegate(self.fetchTable))
        self.fetchTable.setAlternatingRowColors(True)
        self.fetchTable.verticalHeader().setVisible(False)
        self.fetchTable.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.fetchTable.setToolTip("Tick the videos you want, tweak per-video format if needed")
        fetch_hdr = self.fetchTable.horizontalHeader()
        for col, mode in enumerate([
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Interactive
        ]):
            fetch_hdr.setSectionResizeMode(col, mode)

        self.fetchEmptyLabel = QLabel(
            "📋  Nothing fetched yet.\nPaste a YouTube video or playlist URL above and click Fetch."
        )
        self.fetchEmptyLabel.setObjectName("emptyState")
        self.fetchEmptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fetchStack = QStackedWidget()
        self.fetchStack.addWidget(self.fetchTable)       # index 0: has results
        self.fetchStack.addWidget(self.fetchEmptyLabel)  # index 1: empty state
        self.fetchStack.setCurrentIndex(1)

        self.fetch_group = QGroupBox("Fetched Playlist")
        fetch_layout = QVBoxLayout(self.fetch_group)
        fetch_layout.addWidget(self.fetchStack)
        vbox.addWidget(self.fetch_group)

        self.saveEdit = QLineEdit(self.config.default_save_dir)
        self.saveEdit.setToolTip("Folder these downloads will be saved to")
        self.browseBtn = QPushButton("📁 Browse")
        self.browseBtn.setToolTip("Choose a save folder for this download")
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["1080p", "720p", "480p", "360p", "mp3"])
        self.formatCombo.setToolTip("Applies to every video; you can still override individual rows")
        self.srCombo = QComboBox()
        self.srCombo.addItems(["44100", "48000"])
        self.srCombo.setEnabled(False)
        self.srCombo.setToolTip("Sample rate, used only when Format is mp3")
        self.downloadBtn = QPushButton("⬇  Download")
        self.downloadBtn.setObjectName("primaryButton")
        self.downloadBtn.setToolTip("Start downloading the selected videos")
        self.cancelBtn = QPushButton("✖  Cancel")
        self.cancelBtn.setObjectName("dangerButton")
        self.cancelBtn.setToolTip("Stop all downloads and reset")

        # Wrap the full control bar in a group box
        self.controlGroup = QGroupBox("Controls")
        control_layout = QHBoxLayout(self.controlGroup)

        self.logToggleBtn = QPushButton("📄")
        self.logToggleBtn.setObjectName("iconToggle")
        self.logToggleBtn.setToolTip("Show/Hide Log")
        self.logToggleBtn.setCheckable(True)
        self.logToggleBtn.setFixedSize(34, 30)
        self.logToggleBtn.clicked.connect(self._toggle_log_view)
        control_layout.addWidget(self.logToggleBtn)

        self.optToggleBtn = QPushButton("⚙️")
        self.optToggleBtn.setObjectName("iconToggle")
        self.optToggleBtn.setToolTip("Show/Hide Options")
        self.optToggleBtn.setCheckable(True)
        self.optToggleBtn.setFixedSize(34, 30)
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
        
        # Downloading Table
        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        self.downloadTable.hideColumn(2)
        self.downloadTable.setItemDelegateForColumn(3, ProgressBarDelegate(self.downloadTable))
        self.cancelDelegate = CancelButtonDelegate(self.downloadTable)
        self.cancelDelegate.clicked.connect(self._cancel_single_download)
        self.downloadTable.setItemDelegateForColumn(4, self.cancelDelegate)
        self.downloadTable.setAlternatingRowColors(True)
        self.downloadTable.verticalHeader().setVisible(False)
        self.downloadTable.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.downloadTable.setSelectionMode(QTableView.SelectionMode.NoSelection)
        dl_hdr = self.downloadTable.horizontalHeader()
        for col, mode in enumerate([
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Fixed,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Interactive,
            QHeaderView.ResizeMode.Interactive
        ]):
            dl_hdr.setSectionResizeMode(col, mode)

        self.downloadEmptyLabel = QLabel("⬇  Downloads will appear here once you click Download.")
        self.downloadEmptyLabel.setObjectName("emptyState")
        self.downloadEmptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.downloadStack = QStackedWidget()
        self.downloadStack.addWidget(self.downloadTable)       # index 0
        self.downloadStack.addWidget(self.downloadEmptyLabel)  # index 1
        self.downloadStack.setCurrentIndex(1)

        self.download_group = QGroupBox("Download Progress")
        download_layout = QVBoxLayout(self.download_group)
        download_layout.addWidget(self.downloadStack)
        vbox.addWidget(self.download_group)
        vbox.addWidget(self.controlGroup)
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
        self.autoShutdownChk.setToolTip("Shuts down this computer once every download finishes")
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
        self.urlEdit.returnPressed.connect(self._on_url_return_pressed)
        self.fetcher.log.connect(self.logView.append)
        self.fetcher.log.connect(self._on_log_message)

        # Keep the empty-state placeholders in sync with the tables
        self.fetchModel.modelReset.connect(self._update_fetch_stack)
        self.downloadModel.modelReset.connect(self._update_download_stack)

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

    def _on_url_return_pressed(self):
        """Let pressing Enter in the URL field act like clicking Fetch."""
        if self.fetchBtn.isEnabled():
            self.on_fetch_clicked()

    def _update_fetch_stack(self):
        """Show the fetched-playlist table, or a friendly empty state."""
        has_items = self.fetchModel.rowCount() > 0
        if not has_items and self._allFetchedItems and self.searchEdit.text().strip():
            self.fetchEmptyLabel.setText(
                f"🔍  No videos match “{self.searchEdit.text().strip()}”."
            )
        else:
            self.fetchEmptyLabel.setText(
                "📋  Nothing fetched yet.\nPaste a YouTube video or playlist URL above and click Fetch."
            )
        self.fetchStack.setCurrentIndex(0 if has_items else 1)

    def _update_download_stack(self):
        """Show the download-progress table, or a friendly empty state."""
        has_items = self.downloadModel.rowCount() > 0
        self.downloadStack.setCurrentIndex(0 if has_items else 1)

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
    
    def _show_search_view(self):
        self.searchGroup.setVisible(True)
        self.fetchInputGroup.setVisible(False)

    def _show_fetch_input_view(self):
        self.searchGroup.setVisible(False)
        self.fetchInputGroup.setVisible(True)


    def _filter_playlist(self, text):
        text = text.lower().strip()
        #print("Search term:", text)
        #print("Total items stored:", len(self._allFetchedItems))
        if not text:
            self.fetchModel.set_items(self._allFetchedItems)
            return

        filtered = []
        for item in self._allFetchedItems:
            #print("Checking:", item.title)
            if text in item.title.lower():
                filtered.append(item)

        #print("Filtered items:", len(filtered))
        self.fetchModel.set_items(filtered)

    # ── Slot implementations for fetch/download workflows ───────────────────────────

    @pyqtSlot(int)
    def _cancel_single_download(self, row):
        try:
            worker = self.manager._workers[row]
            worker.requestInterruption()
            self.downloadModel.update_status(row, "Canceled")
            self.statusBar().showMessage(f"Canceled download #{row + 1}")
        except Exception as e:
            print(f"Cancel error at row {row}: {e}")

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
        self._allFetchedItems = items
        self._show_search_view()
        self.searchEdit.clear()
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

        # 🔄 Show indeterminate status bar while yt-dlp prepares
        self.sb_progress.setVisible(True)
        self.sb_progress.setRange(0, 0)  # Busy indicator
        self.statusBar().showMessage("Preparing downloads…")

    @pyqtSlot()
    def on_cancel_clicked(self):
        """Cancel all in-progress downloads and reset UI."""

        # 1. Reset fetch input state
        self.urlEdit.clear()
        self.fetchBtn.setEnabled(False)
        self._show_fetch_input_view()

        # 2. Clear the fetched playlist table
        self.fetchModel.set_items([])
        self.fetchHeader._isChecked = False
        self.fetchHeader.updateSection(0)

        # 3. Cancel all ongoing downloads
        self.manager.cancel_all()
        self.downloadModel.set_items([])

        # 4. Restore default save directory
        self.saveEdit.setText(self.config.default_save_dir)

        # 5. Restore control state
        for w in (
            self.fetchBtn, self.urlEdit, self.browseBtn,
            self.downloadBtn, self.formatCombo, self.srCombo
        ):
            w.setEnabled(True)
        self.cancelBtn.setEnabled(False)

        # 6. Disconnect the dynamic "Open Directory" button behavior
        try:
            self.browseBtn.clicked.disconnect(self._open_download_dir)
        except TypeError:
            pass
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.browseBtn.setText("Browse")

        # 7. Clear status bar and hide progress
        self.statusBar().clearMessage()
        self.sb_progress.setVisible(False)

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

        if self.sb_progress.isVisible():
            if self.sb_progress.maximum() == 0:
                # First real download progress → switch to determinate mode
                self.sb_progress.setRange(0, 100)
            self.sb_progress.setValue(int(pct))


    @pyqtSlot(int, str)
    def on_download_finished(self, idx: int, status: str):
        """Handle one video finishing; when all are done, wrap up."""
        self.downloadModel.update_status(idx, status)

        statuses = self.downloadModel.get_statuses()
        if not all(s in ("Completed", "Skipped", "Canceled", "Failed") for s in statuses):
            return

        # Count outcomes
        counts = {"Completed": 0, "Skipped": 0, "Canceled": 0, "Failed": 0}
        for s in statuses:
            if s in counts:
                counts[s] += 1

        # 🧾 Compose summary
        summary = (
            f"✅ {counts['Completed']} completed  "
            f"⚠️ {counts['Canceled']} canceled  "
            f"❌ {counts['Failed']} failed"
        )
        self.statusBar().showMessage(summary)

        # Restore UI
        self.sb_progress.setVisible(False)
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

        self._show_fetch_view()
        self._show_fetch_input_view()

        if self.autoShutdownChk.isChecked():
            if os.name == "nt":
                os.system("shutdown /s /t 60")
            else:
                os.system("shutdown now")


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