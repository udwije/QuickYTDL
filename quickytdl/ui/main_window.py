# quickytdl/ui/main_window.py

import os
import re
from urllib.parse import urlparse, parse_qs
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStyledItemDelegate, QStyle, QStyleOptionButton,
    QStyleOptionProgressBar, QTextEdit, QVBoxLayout, QWidget, QMainWindow,
    QPlainTextEdit, QMenu,
    QTableView, QGroupBox, QStackedWidget, QButtonGroup, QFrame
)
from PyQt6.QtCore import (
    Qt, QThread, QUrl, QRect, pyqtSlot, pyqtSignal, QObject, QEvent, QSize
)
from PyQt6.QtGui import QDesktopServices, QPainter, QIcon, QColor

# Central place to tweak the look of the whole app without hunting through
# every widget constructor. Anything theme-related belongs in theme.py.
from quickytdl.ui import theme


from quickytdl.models import PlaylistTableModel, DownloadTableModel
from quickytdl.fetcher import PlaylistFetcher
from quickytdl.manager import DownloadManager
from quickytdl.config import ConfigManager
from quickytdl.utils import ensure_directory, resource_path, js_runtime_note
from quickytdl import formats

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
    # Colours come from theme.py so they stay legible in both themes.
    dark = False

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
        color = QColor(theme.status_color(status, self.dark))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = option.rect.adjusted(4, 5, -4, -5)

        # Track (unfilled background)
        painter.setPen(Qt.PenStyle.NoPen)
        pal = theme.palette(self.dark)
        painter.setBrush(QColor(pal["hover"]))
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
        painter.setPen(QColor(pal["text"] if percent < 55 else "#ffffff"))
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
    # Batch mode: a list of unrelated URLs rather than one playlist URL.
    batch_request = pyqtSignal(list)
    finished      = pyqtSignal(list)
    error         = pyqtSignal(str)
    log           = pyqtSignal(str)

    def __init__(self, fetcher: PlaylistFetcher):
        super().__init__()
        self.fetcher = fetcher
        self.fetch_request.connect(self._on_fetch, Qt.ConnectionType.QueuedConnection)
        self.batch_request.connect(self._on_batch, Qt.ConnectionType.QueuedConnection)
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

    @pyqtSlot(list)
    def _on_batch(self, urls: list):
        """Triggered when batch_request is emitted."""
        try:
            items = self.fetcher.fetch_urls(
                urls,
                expand_playlists=getattr(self.fetcher, 'batch_expand_playlists', True),
                preselect_playlists=getattr(self.fetcher, 'batch_preselect_playlists', True),
            )
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
        self.setWindowIcon(QIcon(resource_path("resources", "QuickYTDL.png")))

        # Theme defaults to light until the config is loaded below; the real
        # preference is applied once self.config exists.
        self._dark = False

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
        # Now that config is available, honour the saved theme preference.
        self._dark = bool(getattr(self.config, 'dark_mode', False))
        self._apply_theme()
        if not os.path.isdir(self.config.default_save_dir):
            self._prompt_for_default_folder()

        self.fetcher = PlaylistFetcher()
        self.manager = DownloadManager()

        self.fetchModel = PlaylistTableModel([])
        self.downloadModel = DownloadTableModel([])

        self._build_ui()
        self._connect_signals()
        # Re-apply now that every widget exists, so the theme button label
        # and the delegates pick up the current palette.
        self._apply_theme()
        self._update_selection_label()

        self.autoShutdownChk.setChecked(self.config.auto_shutdown)
        self.fetchBtn.setEnabled(False)
        self.downloadBtn.setEnabled(False)
        self.urlEdit.textChanged.connect(self._update_fetch_button_state)
        self.fetchModel.dataChanged.connect(lambda *_: self._update_download_button_state())
        self.fetchModel.dataChanged.connect(lambda *_: self._update_selection_label())
        self.fetchModel.modelReset.connect(self._update_selection_label)
        self.fetchHeader.toggled.connect(lambda _: self._update_download_button_state())

        self._fetch_thread = None
        self._fetch_worker = None

        # Tell the user once if YouTube extraction will be degraded.
        _note = js_runtime_note()
        if _note:
            self._append_log(_note)
            self.statusBar().showMessage(
                "No JavaScript runtime found - some formats may be unavailable.",
                12000,
            )

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
        fetch_input_layout = QVBoxLayout(self.fetchInputGroup)

        # --- single URL row (playlist or one video) ---
        single_row = QHBoxLayout()
        self.urlEdit = QLineEdit()
        self.urlEdit.setPlaceholderText("Paste a YouTube video or playlist URL…")
        self.urlEdit.setToolTip("Paste a YouTube video or playlist URL, then press Enter or click Fetch")
        self.urlEdit.setClearButtonEnabled(True)
        self.fetchBtn = QPushButton("🔎  Fetch")
        self.fetchBtn.setObjectName("primaryButton")
        self.fetchBtn.setToolTip("Look up the video(s) at this URL")
        self.fetchBtn.setDefault(True)
        single_row.addWidget(self.urlEdit)
        single_row.addWidget(self.fetchBtn)
        self.singleUrlWidget = QWidget()
        self.singleUrlWidget.setLayout(single_row)
        fetch_input_layout.addWidget(self.singleUrlWidget)

        # --- batch URL list (many unrelated videos) ---
        self.batchEdit = QPlainTextEdit()
        self.batchEdit.setPlaceholderText(
            "Paste one URL per line (commas also work).\n"
            "Playlist URLs are expanded automatically."
        )
        self.batchEdit.setMaximumHeight(120)
        # NOTE: textChanged is connected further down, once batchModeCheck
        # exists — the handler reads it, so connecting here would raise
        # AttributeError if the signal fired during construction.

        # Playlist policy for batch mode. Defaults: expand playlists, but
        # leave their rows unticked so a 200-video playlist can never start
        # downloading just because one pasted link carried a ?list= param.
        self.expandPlaylistsCheck = QCheckBox("Expand playlist URLs")
        self.expandPlaylistsCheck.setChecked(True)
        self.expandPlaylistsCheck.setToolTip(
            "On: a playlist URL adds all of its videos.\n"
            "Off: only the first video of a playlist URL is added."
        )
        self.preselectPlaylistsCheck = QCheckBox("Pre-select playlist videos")
        self.preselectPlaylistsCheck.setChecked(False)
        self.preselectPlaylistsCheck.setToolTip(
            "Off (recommended): playlist videos are listed but left unticked,\n"
            "so you choose which ones to download.\n"
            "Right-click any row to select or deselect a whole playlist."
        )
        self.expandPlaylistsCheck.toggled.connect(
            lambda on: self.preselectPlaylistsCheck.setEnabled(on)
        )

        batch_opts_row = QHBoxLayout()
        batch_opts_row.addWidget(self.expandPlaylistsCheck)
        batch_opts_row.addWidget(self.preselectPlaylistsCheck)
        batch_opts_row.addStretch(1)

        batch_btn_row = QHBoxLayout()
        self.batchCountLabel = QLabel("0 URLs")
        self.batchFetchBtn = QPushButton("🔎  Fetch All")
        self.batchFetchBtn.setObjectName("primaryButton")
        self.batchFetchBtn.setToolTip("Fetch every URL in the list above")
        batch_btn_row.addWidget(self.batchCountLabel)
        batch_btn_row.addStretch(1)
        batch_btn_row.addWidget(self.batchFetchBtn)

        batch_layout = QVBoxLayout()
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.addWidget(self.batchEdit)
        batch_layout.addLayout(batch_opts_row)
        batch_layout.addLayout(batch_btn_row)
        self.batchWidget = QWidget()
        self.batchWidget.setLayout(batch_layout)
        self.batchWidget.setVisible(False)
        fetch_input_layout.addWidget(self.batchWidget)

        # --- mode switch (segmented control) -----------------------------
        # A checkbox made batch mode feel like an afterthought; two segments
        # present them as equal, obvious choices.
        self.singleModeBtn = QPushButton("Single URL")
        self.singleModeBtn.setObjectName("segmentLeft")
        self.singleModeBtn.setCheckable(True)
        self.singleModeBtn.setChecked(True)
        self.singleModeBtn.setToolTip("Fetch one video or playlist URL")

        self.batchModeBtn = QPushButton("URL List")
        self.batchModeBtn.setObjectName("segmentRight")
        self.batchModeBtn.setCheckable(True)
        self.batchModeBtn.setToolTip("Paste many URLs and fetch them all at once")

        for b in (self.singleModeBtn, self.batchModeBtn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.modeGroup = QButtonGroup(self)
        self.modeGroup.setExclusive(True)
        self.modeGroup.addButton(self.singleModeBtn, 0)
        self.modeGroup.addButton(self.batchModeBtn, 1)

        # Kept for backwards compatibility with the rest of the code, which
        # queries batchModeCheck.isChecked() in several places.
        self.batchModeCheck = QCheckBox()
        self.batchModeCheck.setVisible(False)
        self.batchModeBtn.toggled.connect(self.batchModeCheck.setChecked)
        self.batchModeCheck.toggled.connect(self._toggle_batch_mode)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        mode_row.addWidget(self.singleModeBtn)
        mode_row.addWidget(self.batchModeBtn)
        mode_row.addStretch(1)

        # Theme toggle lives here so it's reachable without opening Options.
        self.themeBtn = QPushButton("🌙  Dark")
        self.themeBtn.setToolTip("Switch between light and dark theme")
        self.themeBtn.setCheckable(True)
        self.themeBtn.clicked.connect(self._toggle_theme)
        mode_row.addWidget(self.themeBtn)

        fetch_input_layout.addLayout(mode_row)

        # Safe to connect now that batchModeCheck exists.
        self.batchEdit.textChanged.connect(self._update_fetch_button_state)
        self.batchFetchBtn.setEnabled(False)

        vbox.addWidget(self.fetchInputGroup)

        # Search option
        """self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search playlist...")
        self.searchEdit.setVisible(True)  # hide until fetched
        self.searchEdit.textChanged.connect(self._filter_playlist)
        vbox.addWidget(self.searchEdit)"""
        # Selection toolbar: search + live selection count + bulk actions.
        # Previously search sat alone in its own group box and the bulk
        # actions were reachable only from a right-click menu, which made
        # them undiscoverable.
        self.searchGroup = QGroupBox("Search")
        search_layout = QVBoxLayout(self.searchGroup)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("🔍  Filter by title or playlist name…")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setToolTip("Type to filter the list below")
        self.searchEdit.textChanged.connect(self._filter_playlist)

        self.selectionLabel = QLabel("0 selected")
        self.selectionLabel.setObjectName("countBadge")
        self.selectionLabel.setToolTip("How many videos will be downloaded")

        self.selAllBtn = QPushButton("All")
        self.selAllBtn.setObjectName("linkButton")
        self.selAllBtn.setToolTip("Select every visible video")
        self.selAllBtn.clicked.connect(lambda: self._bulk_select('all'))

        self.selNoneBtn = QPushButton("None")
        self.selNoneBtn.setObjectName("linkButton")
        self.selNoneBtn.setToolTip("Deselect everything")
        self.selNoneBtn.clicked.connect(lambda: self._bulk_select('none'))

        self.selInvertBtn = QPushButton("Invert")
        self.selInvertBtn.setObjectName("linkButton")
        self.selInvertBtn.setToolTip("Flip the selection")
        self.selInvertBtn.clicked.connect(lambda: self._bulk_select('invert'))

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.VLine)

        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 6, 8, 6)
        tb.setSpacing(6)
        tb.addWidget(self.searchEdit, 1)
        tb.addWidget(sep)
        tb.addWidget(self.selectionLabel)
        tb.addWidget(QLabel("Select:"))
        tb.addWidget(self.selAllBtn)
        tb.addWidget(self.selNoneBtn)
        tb.addWidget(self.selInvertBtn)

        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(toolbar)
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
        # Format moved to column 4 now that Source occupies column 3.
        self.fetchTable.setItemDelegateForColumn(4, FormatDelegate(self.fetchTable))

        self.fetchTable.setAlternatingRowColors(True)
        self.fetchTable.verticalHeader().setVisible(False)
        self.fetchTable.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.fetchTable.setToolTip(
            "Tick the videos you want, tweak per-video format if needed.\n"
            "Right-click a row to act on its whole source."
        )

        # Right-click a row to act on every row from the same pasted URL.
        self.fetchTable.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fetchTable.customContextMenuRequested.connect(self._show_source_menu)

        fetch_hdr = self.fetchTable.horizontalHeader()
        for col, mode in enumerate([
            QHeaderView.ResizeMode.Interactive,   # Select
            QHeaderView.ResizeMode.Interactive,   # Video No
            QHeaderView.ResizeMode.Stretch,       # Description
            QHeaderView.ResizeMode.Interactive,   # Source
            QHeaderView.ResizeMode.Interactive    # Format
        ]):
            fetch_hdr.setSectionResizeMode(col, mode)
        self.fetchEmptyLabel = QLabel(
            "📋  Nothing fetched yet.\n"
            "Paste a YouTube video or playlist URL above and click Fetch,\n"
            "or switch on Batch mode to paste a whole list of URLs."
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
        self.formatCombo.addItems(formats.ALL_FORMATS)
        # Default to 'best' so a 4K source is taken at 4K without the user
        # having to pick a tier that may not exist on every playlist item.
        self.formatCombo.setCurrentText(formats.BEST)
        self.formatCombo.setToolTip(
            "Tiers above 1080p are saved as .mkv — YouTube has no MP4 above "
            "1080p. If an item lacks the chosen resolution, the next best "
            "available is used."
        )
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
        self.logToggleBtn.setFixedWidth(30)
        self.logToggleBtn.clicked.connect(self._toggle_log_view)
        control_layout.addWidget(self.logToggleBtn)

        self.optToggleBtn = QPushButton("⚙️")
        self.optToggleBtn.setObjectName("iconToggle")
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
        
        # Downloading Table
        self.downloadTable = QTableView()
        self.downloadTable.setModel(self.downloadModel)
        self.downloadTable.hideColumn(2)
        self.progressDelegate = ProgressBarDelegate(self.downloadTable)
        self.progressDelegate.dark = self._dark
        self.downloadTable.setItemDelegateForColumn(3, self.progressDelegate)
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

        # Overall progress across the whole queue. Per-row bars alone make
        # it hard to answer "how far along is this batch?".
        self.overallBar = QProgressBar()
        self.overallBar.setRange(0, 100)
        self.overallBar.setValue(0)
        self.overallBar.setFixedHeight(16)
        self.overallBar.setToolTip("Combined progress across all downloads")

        self.overallLabel = QLabel("0 of 0 complete")
        self.overallLabel.setObjectName("countBadge")

        overall_row = QHBoxLayout()
        overall_row.setContentsMargins(0, 0, 0, 6)
        overall_row.addWidget(QLabel("Overall:"))
        overall_row.addWidget(self.overallBar, 1)
        overall_row.addWidget(self.overallLabel)

        self.download_group = QGroupBox("Download Progress")
        download_layout = QVBoxLayout(self.download_group)
        download_layout.addLayout(overall_row)
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
        self.batchFetchBtn.clicked.connect(self.on_batch_fetch_clicked)
        self.urlEdit.returnPressed.connect(self._on_url_return_pressed)

        # Keep the empty-state placeholders in sync with the tables
        self.fetchModel.modelReset.connect(self._update_fetch_stack)
        self.downloadModel.modelReset.connect(self._update_download_stack)
        self.fetcher.log.connect(self.logView.append)
        self.fetcher.log.connect(self._on_log_message)

        # Browse dialogs
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)

        # Download controls
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)
        self.formatCombo.currentTextChanged.connect(
            lambda fmt: self.srCombo.setEnabled(fmt == formats.MP3)
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

    @staticmethod
    def parse_url_list(text: str) -> list:
        """
        Split pasted text into candidate URLs.

        Accepts newline and/or comma separation, ignores blank lines and
        '#' comments, and keeps only http(s) entries so stray notes in a
        pasted block don't become failed fetches. Order is preserved and
        duplicates are dropped (the fetcher dedupes too, but doing it here
        keeps the live count honest).
        """
        urls, seen = [], set()
        for chunk in re.split(r'[\s,]+', text or ""):
            u = chunk.strip()
            if not u or u.startswith('#'):
                continue
            if not re.match(r'^https?://', u, re.IGNORECASE):
                continue
            if u not in seen:
                seen.add(u)
                urls.append(u)
        return urls

    def _toggle_batch_mode(self, on: bool):
        """Switch between single-URL and batch-list input."""
        self.singleUrlWidget.setVisible(not on)
        self.batchWidget.setVisible(on)
        self.fetchInputGroup.setTitle(
            "Fetch URL List" if on else "Fetch Playlist"
        )
        self._update_fetch_button_state()

    def _update_fetch_button_state(self):
        """Enable Fetch/Fetch All only when there's something valid to fetch."""
        if self.batchModeCheck.isChecked():
            urls = self.parse_url_list(self.batchEdit.toPlainText())
            n = len(urls)
            self.batchCountLabel.setText(f"{n} URL{'s' if n != 1 else ''}")
            self.batchFetchBtn.setEnabled(n > 0)
            self.fetchBtn.setEnabled(False)
        else:
            txt = self.urlEdit.text().strip()
            ok = bool(txt) and QUrl(txt).isValid()
            self.fetchBtn.setEnabled(ok)
            self.batchFetchBtn.setEnabled(False)

    def _on_url_return_pressed(self):
        """Let pressing Enter in the URL field act like clicking Fetch."""
        if self.fetchBtn.isEnabled():
            self.on_fetch_clicked()

    def _update_fetch_stack(self):
        """Show the fetched table, or a friendly empty state."""
        has_items = self.fetchModel.rowCount() > 0
        if not has_items and self._allFetchedItems and self.searchEdit.text().strip():
            self.fetchEmptyLabel.setText(
                f"🔍  No videos match \u201c{self.searchEdit.text().strip()}\u201d."
            )
        else:
            self.fetchEmptyLabel.setText(
                "📋  Nothing fetched yet.\n"
                "Paste a YouTube video or playlist URL above and click Fetch,\n"
                "or switch on Batch mode to paste a whole list of URLs."
            )
        self.fetchStack.setCurrentIndex(0 if has_items else 1)

    def _update_download_stack(self):
        """Show the download-progress table, or a friendly empty state."""
        has_items = self.downloadModel.rowCount() > 0
        self.downloadStack.setCurrentIndex(0 if has_items else 1)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        """Apply the current theme to the window and repaint the tables."""
        self.setStyleSheet(theme.stylesheet(self._dark))
        # The progress delegate paints outside the stylesheet, so it needs
        # telling which palette to draw against.
        for attr in ('progressDelegate',):
            d = getattr(self, attr, None)
            if d is not None:
                d.dark = self._dark
        if hasattr(self, 'themeBtn'):
            self.themeBtn.setChecked(self._dark)
            self.themeBtn.setText("☀️  Light" if self._dark else "🌙  Dark")
        for t in ('fetchTable', 'downloadTable'):
            w = getattr(self, t, None)
            if w is not None:
                w.viewport().update()

    def _toggle_theme(self):
        """Flip light/dark and remember the choice."""
        self._dark = not self._dark
        self.config.dark_mode = self._dark
        try:
            self.config.save()
        except Exception:
            pass
        self._apply_theme()

    # ------------------------------------------------------------------
    # Bulk selection
    # ------------------------------------------------------------------

    def _bulk_select(self, mode: str):
        """
        Apply a bulk selection action to the rows currently VISIBLE in the
        table. Operating on the filtered view (not the whole fetch) is what
        makes "search, then select all" work as users expect.
        """
        items = getattr(self.fetchModel, '_items', [])
        if not items:
            return
        for it in items:
            if mode == 'all':
                it.selected = True
            elif mode == 'none':
                it.selected = False
            elif mode == 'invert':
                it.selected = not getattr(it, 'selected', False)
        self._refresh_fetch_table()
        self._sync_header_checkbox()
        self._update_download_button_state()
        self._update_selection_label()

    def _update_overall_progress(self):
        """
        Aggregate the per-row percentages into one queue-wide bar so the
        user can see how far along the whole batch is at a glance.
        """
        if not hasattr(self, 'overallBar'):
            return
        items = getattr(self.downloadModel, '_items', []) or []
        total = len(items)
        if not total:
            self.overallBar.setValue(0)
            self.overallLabel.setText("0 of 0 complete")
            return

        terminal = ("Completed", "Skipped", "Canceled", "Failed")
        done = sum(1 for it in items if getattr(it, 'status', '') in terminal)
        # A finished row counts as 100% regardless of its last reported pct.
        pct_sum = sum(
            100.0 if getattr(it, 'status', '') in terminal
            else float(getattr(it, 'progress', 0) or 0)
            for it in items
        )
        self.overallBar.setValue(int(pct_sum / total))

        failed = sum(1 for it in items if getattr(it, 'status', '') == "Failed")
        text = f"{done} of {total} complete"
        if failed:
            text += f" · {failed} failed"
        self.overallLabel.setText(text)

    def _update_selection_label(self):
        """Live 'N of M selected' badge above the table."""
        if not hasattr(self, 'selectionLabel'):
            return
        all_items = self._allFetchedItems or []
        total = len(all_items)
        sel = sum(1 for it in all_items if getattr(it, 'selected', False))

        visible = len(getattr(self.fetchModel, '_items', []))
        if visible != total:
            self.selectionLabel.setText(f"{sel} of {total} selected · {visible} shown")
        else:
            self.selectionLabel.setText(f"{sel} of {total} selected")

        for b in ('selAllBtn', 'selNoneBtn', 'selInvertBtn'):
            btn = getattr(self, b, None)
            if btn is not None:
                btn.setEnabled(total > 0)

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
            # Match the source/playlist name too, so a user can isolate one
            # pasted URL's videos and act on just those.
            src = (getattr(item, 'source_title', '') or '').lower()
            if text in item.title.lower() or (src and text in src):
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

    def _start_fetch_thread(self):
        """
        Reset state and spin up the fetch worker/thread.
        Returns the worker so the caller can emit the right request signal.
        """
        if self._fetch_thread:
            self._cleanup_fetch_thread()

        self.fetchModel.set_items([])
        self.logView.clear()

        self.fetchBtn.setEnabled(False)
        self.batchFetchBtn.setEnabled(False)

        self._fetch_thread = QThread(self)
        self._fetch_worker = FetchWorker(self.fetcher)
        self._fetch_worker.moveToThread(self._fetch_thread)

        self._fetch_worker.finished.connect(self._handle_fetch_done)
        self._fetch_worker.error.connect(self._handle_fetch_error)
        self._fetch_thread.finished.connect(self._cleanup_fetch_thread)

        self._fetch_thread.start()
        return self._fetch_worker

    def _after_fetch_started(self, select_all: bool = True):
        """
        Switch to the fetch view. select_all=False for batch mode, where the
        per-row selection is decided by the playlist policy instead.
        """
        self.fetchHeader._isChecked = bool(select_all)
        self.fetchHeader.updateSection(0)
        if select_all:
            self.on_select_all(True)
        self._show_fetch_view()

    @pyqtSlot()
    def on_fetch_clicked(self):
        """Start or restart playlist metadata fetch (single URL)."""
        url = self.urlEdit.text().strip()
        if not url:
            return

        worker = self._start_fetch_thread()
        worker.fetch_request.emit(url)
        self._after_fetch_started()

    @staticmethod
    def looks_like_playlist(url: str) -> bool:
        """
        Cheap, offline guess at whether a URL will expand into a playlist.
        Used only to decide whether to bother asking the user — the real
        answer comes from yt-dlp during the fetch.
        """
        u = (url or "").lower()
        # Mixes/radio, Liked and Watch-later can't be enumerated by YouTube,
        # so they always collapse to the single video — never prompt for them.
        if PlaylistFetcher._is_unlistable_playlist(url):
            return False
        if '/playlist' in u:
            return True
        # A ?list= param on a watch URL also expands.
        try:
            qs = parse_qs(urlparse(u).query)
        except Exception:
            return False
        return bool(qs.get('list'))

    def _confirm_playlist_expansion(self, urls: list) -> str:
        """
        Ask before expanding playlist URLs in a batch.

        Returns 'expand', 'first-only', or 'cancel'. Returns 'expand'
        immediately when no URL looks like a playlist, so the common case
        of pasting plain video links stays friction-free.
        """
        likely = [u for u in urls if self.looks_like_playlist(u)]
        if not likely:
            return 'expand'

        preview = "\n".join(likely[:10])
        if len(likely) > 10:
            preview += f"\n… and {len(likely) - 10} more"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Playlist URL detected")
        box.setText(
            f"{len(likely)} of your {len(urls)} URL(s) point to a playlist."
        )
        box.setInformativeText(
            "Expanding adds every video in those playlists, which could be "
            "hundreds of rows.\n\n"
            "Expanded videos are listed unticked, so nothing downloads until "
            "you select it."
        )
        box.setDetailedText(preview)

        b_expand = box.addButton("Expand playlists",
                                 QMessageBox.ButtonRole.AcceptRole)
        b_first = box.addButton("First video only",
                                QMessageBox.ButtonRole.DestructiveRole)
        b_cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        # Default to the safe option so a reflexive Enter doesn't expand.
        box.setDefaultButton(b_first)
        box.exec()

        clicked = box.clickedButton()
        if clicked is b_cancel or clicked is None:
            return 'cancel'
        return 'expand' if clicked is b_expand else 'first-only'

    @pyqtSlot()
    def on_batch_fetch_clicked(self):
        """Fetch metadata for a pasted list of unrelated URLs."""
        urls = self.parse_url_list(self.batchEdit.toPlainText())
        if not urls:
            return

        # Remember the policy for this run; _handle_fetch_done needs to know
        # whether to blanket-select every row afterwards.
        self._batch_expand = self.expandPlaylistsCheck.isChecked()

        # If the user asked to expand and the list actually contains playlist
        # links, confirm first — expanding can turn 1 pasted line into
        # hundreds of rows, and that should never be a surprise.
        if self._batch_expand:
            choice = self._confirm_playlist_expansion(urls)
            if choice == 'cancel':
                self._update_fetch_button_state()
                return
            self._batch_expand = (choice == 'expand')

        self._batch_preselect = (
            self.preselectPlaylistsCheck.isChecked() and self._batch_expand
        )
        self.fetcher.batch_expand_playlists = self._batch_expand
        self.fetcher.batch_preselect_playlists = self._batch_preselect

        worker = self._start_fetch_thread()
        worker.batch_request.emit(urls)
        self._after_fetch_started(select_all=False)

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

        # In batch mode the fetcher has already decided each row's selected
        # state from the playlist policy, so don't blanket-select here —
        # that would re-tick a 200-video playlist the user chose to skip.
        batch_mode = self.batchModeCheck.isChecked()

        fmt = self.formatCombo.currentText()
        for it in items:
            if not batch_mode:
                it.selected = True
            elif not hasattr(it, 'selected'):
                it.selected = True
            it.format_overridden = False
            # Fall back to 'best' when the chosen tier isn't offered for
            # this item, so selected_format is never left unset.
            it.selected_format = fmt if fmt in it.available_formats else formats.BEST

        if batch_mode:
            n_sel = sum(1 for it in items if getattr(it, 'selected', False))
            n_pl = sum(1 for it in items if getattr(it, 'from_playlist', False))
            if n_pl:
                self.statusBar().showMessage(
                    f"{len(items)} videos ({n_pl} from playlists) — "
                    f"{n_sel} selected. Right-click a row to select/deselect "
                    f"a whole playlist.", 15000
                )
            self._sync_header_checkbox(items)

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
            self.browseBtn, self.formatCombo, self.srCombo,
            self.batchEdit, self.batchFetchBtn, self.batchModeCheck,
            self.singleModeBtn, self.batchModeBtn,
            self.expandPlaylistsCheck, self.preselectPlaylistsCheck
        ):
            w.setEnabled(False)
        self.cancelBtn.setEnabled(True)

        sel = self.fetchModel.get_selected_items()
        if not sel:
            return

        fmt = self.formatCombo.currentText()
        sr = int(self.srCombo.currentText()) if fmt == formats.MP3 else None
        for it in sel:
            # Respect a per-row override set via the Format column; only
            # fall back to the global selector when the user hasn't picked
            # one for that row.
            if not getattr(it, 'format_overridden', False):
                it.selected_format = fmt
            if getattr(it, 'selected_format', None) not in formats.ALL_FORMATS:
                it.selected_format = fmt
            row_fmt = it.selected_format
            setattr(
                it, 'sample_rate',
                int(self.srCombo.currentText()) if row_fmt == formats.MP3 else None
            )

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
        self.batchEdit.clear()
        self.fetchBtn.setEnabled(False)
        self.batchFetchBtn.setEnabled(False)
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
            self.downloadBtn, self.formatCombo, self.srCombo,
            self.batchEdit, self.batchModeCheck,
            self.singleModeBtn, self.batchModeBtn,
            self.expandPlaylistsCheck, self.preselectPlaylistsCheck
        ):
            w.setEnabled(True)
        self._update_fetch_button_state()
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
        self._update_overall_progress()

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
        self._update_overall_progress()

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
            self.saveEdit, self.formatCombo, self.srCombo,
            self.batchEdit, self.batchModeCheck,
            self.singleModeBtn, self.batchModeBtn,
            self.expandPlaylistsCheck, self.preselectPlaylistsCheck
        ):
            w.setEnabled(True)
        self._update_fetch_button_state()

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

    def _show_source_menu(self, pos):
        """
        Right-click menu on the fetched table, for acting on every row that
        came from the same pasted URL. This is how a user drops the rest of
        a playlist they didn't mean to expand.
        """
        index = self.fetchTable.indexAt(pos)
        if not index.isValid():
            return
        try:
            item = self.fetchModel._items[index.row()]
        except (IndexError, AttributeError):
            return

        src_url = getattr(item, 'source_url', None) or item.url
        src_title = getattr(item, 'source_title', '') or item.title
        is_pl = bool(getattr(item, 'from_playlist', False))

        # Count siblings so the menu can say how many rows it will affect.
        siblings = [
            it for it in self.fetchModel._items
            if (getattr(it, 'source_url', None) or it.url) == src_url
        ]
        n = len(siblings)

        label = src_title if len(src_title) <= 40 else src_title[:39] + "…"

        menu = QMenu(self)
        if is_pl or n > 1:
            header = menu.addAction(f"Playlist: {label}  ({n} videos)"
                                    if is_pl else f"Source: {label}  ({n} videos)")
            header.setEnabled(False)
            menu.addSeparator()

            act_sel = menu.addAction(f"Select all {n} from this source")
            act_desel = menu.addAction(f"Deselect all {n} from this source")
            act_only = menu.addAction("Select only this source")
            menu.addSeparator()
            act_keep_one = menu.addAction("Keep only this video (drop the rest)")
        else:
            header = menu.addAction(f"Source: {label}")
            header.setEnabled(False)
            menu.addSeparator()
            act_sel = act_desel = act_only = act_keep_one = None

        menu.addSeparator()
        act_all = menu.addAction("Select all rows")
        act_none = menu.addAction("Deselect all rows")

        chosen = menu.exec(self.fetchTable.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen is act_sel:
            self.fetchModel.set_source_selected(src_url, True)
        elif chosen is act_desel:
            self.fetchModel.set_source_selected(src_url, False)
        elif chosen is act_only:
            self.fetchModel.keep_only_source(src_url)
        elif chosen is act_keep_one:
            # Deselect everything, then re-tick just the clicked row.
            for it in self.fetchModel._items:
                it.selected = (it is item)
            self._refresh_fetch_table()
        elif chosen is act_all:
            self.on_select_all(True)
        elif chosen is act_none:
            self.on_select_all(False)

        self._refresh_fetch_table()
        self._sync_header_checkbox()
        self._update_download_button_state()

    def _sync_header_checkbox(self, items=None):
        """Keep the header select-all box consistent with the rows."""
        items = items if items is not None else self.fetchModel._items
        if not items:
            return
        all_on = all(getattr(it, 'selected', False) for it in items)
        self.fetchHeader._isChecked = all_on
        self.fetchHeader.updateSection(0)

    def _refresh_fetch_table(self):
        """Repaint the whole fetched table after a bulk selection change."""
        if self.fetchModel.rowCount() == 0:
            return
        top = self.fetchModel.index(0, 0)
        bot = self.fetchModel.index(
            self.fetchModel.rowCount() - 1,
            self.fetchModel.columnCount() - 1
        )
        self.fetchModel.dataChanged.emit(
            top, bot, [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.DisplayRole]
        )

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
