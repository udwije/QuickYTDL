# quickytdl/models.py

from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QVariant
)


class PlaylistTableModel(QAbstractTableModel):
    """
    Table model for the fetched playlist.
    Columns: [Select, Video No, Description, Format]
    """
    HEADERS = ["Select", "Video No", "Description", "Format"]

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

        # Format (editable combo box)
        if col == 3 and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return item.selected_format

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
        if col == 3:
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsSelectable
            )
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

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
        if col == 3 and role == Qt.ItemDataRole.EditRole:
            if value in item.available_formats:
                item.selected_format = value
                self.dataChanged.emit(index, index, [role])
                return True

        return False

    def set_items(self, items):
        """
        Replace model items. Initialize selection and formats.
        """
        self.beginResetModel()
        self._items = items
        for it in self._items:
            it.selected = False
            # default selected_format to first available or empty
            it.selected_format = it.available_formats[0] if it.available_formats else ""
        self.endResetModel()

    def get_selected_items(self):
        """Return list of items where selected==True."""
        return [it for it in self._items if getattr(it, "selected", False)]


class DownloadTableModel(QAbstractTableModel):
    """
    Table model for download status.
    Columns: [Video No, Description, Format, Progress, Status]
    """
    HEADERS = ["Video No", "Description", "Format", "Progress", "Status"]

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
                # show percent, e.g. "42%"
                return f"{int(item.progress)}%"
            if col == 4:
                return item.status

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # all cells read-only
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_items(self, items):
        """
        Initialize download items: set progress=0 and status='Queued'.
        """
        self.beginResetModel()
        self._items = items
        for it in self._items:
            it.progress = 0
            it.status = "Queued"
        self.endResetModel()

    def update_progress(self, row, percent, status):
        """
        Called during download to update progress bar and status text.
        """
        if 0 <= row < len(self._items):
            it = self._items[row]
            it.progress = percent
            it.status = status
            left = self.index(row, 3)
            right = self.index(row, 4)
            self.dataChanged.emit(left, right, [Qt.ItemDataRole.DisplayRole])

    def update_status(self, row, status):
        """
        Called when a download finishes (or fails).
        """
        if 0 <= row < len(self._items):
            it = self._items[row]
            it.status = status
            idx = self.index(row, 4)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def get_statuses(self):
        """Return list of status strings for all rows."""
        return [it.status for it in self._items]
