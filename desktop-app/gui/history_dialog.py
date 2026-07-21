import os
import sys
import subprocess
import time
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView
)


class HistoryDialog(QDialog):
    def __init__(self, history_entries, on_clear=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download History")
        self.setMinimumSize(700, 400)
        self.on_clear = on_clear

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Filename", "Size", "Status", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)

        self.entries = history_entries
        self.populate()

        btn_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear History")
        self.close_btn = QPushButton("Close")
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def populate(self):
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            size_mb = (entry.get("size_bytes") or 0) / (1024 * 1024)
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get("timestamp", 0)))

            self.table.setItem(row, 0, QTableWidgetItem(entry.get("filename", "")))
            self.table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.2f} MB"))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("status", "")))
            self.table.setItem(row, 3, QTableWidgetItem(date_str))

    def on_row_double_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self.entries):
            return
        path = self.entries[row].get("path", "")
        if not path or not os.path.exists(path):
            return
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            print(f"Failed to open file location: {e}")

    def on_clear_clicked(self):
        if self.on_clear:
            self.on_clear()
        self.entries = []
        self.populate()