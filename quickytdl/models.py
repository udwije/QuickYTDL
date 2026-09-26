# quickytdl/models.py

from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QVariant
)


class PlaylistTableModel(QAbstractTableModel):
    """
    Table model for the fetched playlist.
    Columns: [Select, Video No, Description, Source, Format]
    """
    HEADERS = ["Select", "Video No", "Description", "Source", "Format"]

    def __init__(self, items=None):
        super().__init__()
        self._items = []
        if items:
            self.set_items(items)

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()

        # Checkbox column
        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if item.selected else Qt.CheckState.Unchecked

        # Video No
        if col == 1 and role == Qt.ItemDataRole.DisplayRole:
            return str(item.index)

        # Description
        if col == 2 and role == Qt.ItemDataRole.DisplayRole:
            return item.title

        # Source (which pasted URL this row came from)
        if col == 3 and role == Qt.ItemDataRole.DisplayRole:
            if getattr(item, 'from_playlist', False):
                return getattr(item, 'source_title', '') or ''
            return ''

        # Format (editable combo box)
        if col == 4 and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return item.selected_format

        # Tooltip: show the originating URL on any column.
        if role == Qt.ItemDataRole.ToolTipRole:
            src = getattr(item, 'source_url', None)
            if getattr(item, 'from_playlist', False):
                return (f"From playlist: {getattr(item, 'source_title', '')}\n{src}\n"
                        f"Right-click to select/deselect this whole playlist.")
            return src or None

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        col = index.column()
        if col == 0:
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
        if col == 4:
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsSelectable
            )
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # ------------------------------------------------------------------
    # Source-group helpers (batch mode)
    # ------------------------------------------------------------------

    def sources(self) -> list:
        """
        Distinct (source_url, source_title, count, from_playlist) in the
        order they first appear. Used to drive the source context menu.
        """
        out, seen = [], {}
        for it in self._items:
            key = getattr(it, 'source_url', None) or it.url
            if key not in seen:
                seen[key] = len(out)
                out.append([key, getattr(it, 'source_title', '') or it.title,
                            0, bool(getattr(it, 'from_playlist', False))])
            out[seen[key]][2] += 1
        return [tuple(r) for r in out]

    def set_source_selected(self, source_url: str, selected: bool) -> int:
        """
        Tick/untick every row belonging to one source URL.
        Returns how many rows changed.
        """
        changed = 0
        for row, it in enumerate(self._items):
            key = getattr(it, 'source_url', None) or it.url
            if key == source_url and bool(it.selected) != bool(selected):
                it.selected = bool(selected)
                changed += 1
        if changed:
            top = self.index(0, 0)
            bot = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bot, [Qt.ItemDataRole.CheckStateRole])
        return changed

    def keep_only_source(self, source_url: str) -> int:
        """Select every row of one source and deselect all others."""
        changed = 0
        for it in self._items:
            key = getattr(it, 'source_url', None) or it.url
            want = (key == source_url)
            if bool(it.selected) != want:
                it.selected = want
                changed += 1
        if changed:
            top = self.index(0, 0)
            bot = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bot, [Qt.ItemDataRole.CheckStateRole])
        return changed

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        item = self._items[index.row()]
        col = index.column()

        # toggle selection
        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            item.selected = (value == Qt.CheckState.Checked)
            self.dataChanged.emit(index, index, [role])
            return True

        # change selected format
        if col == 4 and role == Qt.ItemDataRole.EditRole:
            if value in item.available_formats:
                item.selected_format = value
                # Mark it so the global Format selector no longer clobbers
                # this row when the download starts.
                item.format_overridden = True
                self.dataChanged.emit(index, index, [role])
                return True

        return False

    def set_items(self, items):
        """
        Initialize download items: set progress=0, status='Queued',
        and clear any previous speed/eta.
        """
        self.beginResetModel()
        self._items = items
        for it in self._items:
            it.progress = 0
            it.status = "Queued"
            # ensure speed/eta fields exist
            it.speed = ""
            it.eta   = ""
        self.endResetModel()

    def get_selected_items(self):
        """Return list of items where selected==True."""
        return [it for it in self._items if getattr(it, "selected", False)]


class DownloadTableModel(QAbstractTableModel):
    """
    Table model for download status.
    Columns: [Video No, Description, Format, Progress, Cancel, Status]
    """
    HEADERS = ["Video No", "Description", "Format", "Progress", "Cancel", "Status"]

    def __init__(self, items=None):
        super().__init__()
        self._items = []
        if items:
            self.set_items(items)

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(item.index)
            if col == 1:
                return item.title
            if col == 2:
                return item.selected_format
            if col == 3:
                # Progress column: "42% │ 1.2MiB/s │ ETA 00:12"
                pct = int(item.progress)
                parts = [f"{pct}%"]
                if getattr(item, "speed", ""):
                    parts.append(item.speed)
                if getattr(item, "eta", ""):
                    parts.append(f"ETA {item.eta}")
                return " │ ".join(parts)
            if col == 4:
                return ""  # Placeholder: rendered by CancelButtonDelegate
            if col == 5:
                return item.status

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_items(self, items):
        self.beginResetModel()
        self._items = items
        for it in self._items:
            it.progress = 0
            it.status = "Queued"
        self.endResetModel()

    def update_progress(self, row, percent, status):
        if 0 <= row < len(self._items):
            it = self._items[row]
            it.progress = percent
            it.status = status
            # update columns: Progress, Cancel, Status
            left = self.index(row, 3)
            right = self.index(row, 5)
            self.dataChanged.emit(left, right, [Qt.ItemDataRole.DisplayRole])

    def update_status(self, row, status):
        if 0 <= row < len(self._items):
            it = self._items[row]
            it.status = status
            idx = self.index(row, 5)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def get_statuses(self):
        return [it.status for it in self._items]

