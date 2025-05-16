from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QCheckBox, QWidget, QHBoxLayout, QProgressBar
)
from PyQt5.QtCore import Qt

class PlaylistTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 5, parent)  # Changed to 5 columns
        self.setHorizontalHeaderLabels(["✔", "Title", "Duration", "Status", "Progress"])
        self.setColumnWidth(0, 30)

    def populate_table(self, items):
        self.setRowCount(0)
        for item in items:
            row = self.rowCount()
            self.insertRow(row)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(item.get("selected", True))
            checkbox_widget = QWidget()
            layout = QHBoxLayout(checkbox_widget)
            layout.addWidget(checkbox)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(row, 0, checkbox_widget)

            # Title
            self.setItem(row, 1, QTableWidgetItem(item.get("title", "")))
            # Duration
            self.setItem(row, 2, QTableWidgetItem(str(item.get("duration", ""))))
            # Status
            self.setItem(row, 3, QTableWidgetItem(item.get("status", "⏳")))
            # Progress
            progress_bar = QProgressBar()
            progress_bar.setValue(0)
            progress_bar.setAlignment(Qt.AlignCenter)
            self.setCellWidget(row, 4, progress_bar)



    def get_selected_items(self):
        items = []
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            checkbox = checkbox_widget.layout().itemAt(0).widget()
            if checkbox.isChecked():
                items.append({
                    "title": self.item(row, 1).text(),
                    "duration": self.item(row, 2).text(),
                    "status": self.item(row, 3).text(),
                })
        return items

    def update_status(self, row, status_text):
        if 0 <= row < self.rowCount():
            self.setItem(row, 3, QTableWidgetItem(status_text))

    def update_progress_bar(self, row, percent):
        if 0 <= row < self.rowCount():
            progress_bar = self.cellWidget(row, 4)
            if isinstance(progress_bar, QProgressBar):
                progress_bar.setValue(percent)
