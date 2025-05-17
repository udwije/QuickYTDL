# quickytdl/ui/main_window.py

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLineEdit, QComboBox, QPushButton,
    QTableView, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QLabel, QMessageBox,
    QStyledItemDelegate, QHeaderView,
    QStyleOptionProgressBar, QStyle, QApplication,
    QStyleOptionButton, QStyleOptionViewItem, QCheckBox
)
from PyQt6.QtCore import (
    pyqtSlot, Qt, QThread, QObject, pyqtSignal, QRect
)

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
    """Renders a progress bar with centered percentage text."""
    def paint(self, painter, option, index):
        # pull raw data, strip any trailing '%' and safely convert to int
        raw = index.data()
        try:
            if isinstance(raw, str) and raw.endswith('%'):
                raw = raw[:-1]
            value = int(raw)
        except (ValueError, TypeError):
            value = 0
        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = value
        opt.text = f"{value}%"
        opt.textVisible = True
        opt.textAlignment = Qt.AlignmentFlag.AlignCenter
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
        self.setWindowTitle("QuickYTDL")
        self.resize(1000, 700)

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

        # install header-checkbox in column-0
        header = CheckBoxHeader(
            Qt.Orientation.Horizontal, self.fetchTable
        )
        # store header so we can reset it later on cancel
        self.fetchHeader = CheckBoxHeader(Qt.Orientation.Horizontal, self.fetchTable)
        self.fetchTable.setHorizontalHeader(header)
        self.fetchHeader = header  # store for later
        header.toggled.connect(self.on_select_all)

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
        self.formatCombo.addItems(
            ["1080p", "720p", "480p", "360p"]
        )
        self.formatCombo.setStyleSheet(
            "background-color: #c8e6c9;"
        )
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
        self.fetchBtn.clicked.connect(self.on_fetch_clicked)

        # Browse
        self.browseBtn.clicked.connect(self.on_browse_save)
        self.defBrowseBtn.clicked.connect(self.on_browse_default)

        # Download / Cancel
        self.downloadBtn.clicked.connect(self.on_download_clicked)
        self.cancelBtn.clicked.connect(self.on_cancel_clicked)

        # Auto-shutdown
        self.autoShutdownChk.stateChanged.connect(
            self.on_auto_shutdown_changed
        )

        # Download events
        self.manager.progress.connect(self.on_download_progress)
        self.manager.finished.connect(self.on_download_finished)
        self.manager.log.connect(self.logView.append)

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

        # default to all selected
        self.fetchHeader._isChecked = True
        self.fetchHeader.updateSection(0)
        self.on_select_all(True)

    @pyqtSlot(list)
    def _handle_fetch_done(self, items: list):
        self.fetchBtn.setEnabled(True)
        self.fetchModel.set_items(items)

        # Apply global format to each item
        fmt = self.formatCombo.currentText()
        for it in items:
            it.selected = True
            if fmt in it.available_formats:
                it.selected_format = fmt

        # Color-code global-format dropdown
        common = set.intersection(*(set(it.available_formats)
                                   for it in items))
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

        save_dir = (
            self.saveEdit.text().strip()
            or self.config.default_save_dir
        )
        ensure_directory(save_dir)
        self.downloadModel.set_items(sel)
        self.manager.start_downloads(sel, save_dir)

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
        if hasattr(self, "fetchHeader"):
            self.fetchHeader._isChecked = False
            self.fetchHeader.updateSection(0)

        # 5) Unblock every UI control so the user can start fresh
        self.fetchBtn.setEnabled(True)
        self.urlEdit.setEnabled(True)
        self.browseBtn.setEnabled(True)
        self.downloadBtn.setEnabled(True)

    @pyqtSlot(int, float, str)
    def on_download_progress(self, idx: int, pct: float, status: str):
        self.downloadModel.update_progress(idx, pct, status)

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
