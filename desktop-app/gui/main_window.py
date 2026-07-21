import os
import sys
import subprocess
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QPushButton,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from downloader.categorizer import ALL_CATEGORIES
from downloader.history_manager import load_history, clear_history


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Downloader")
        self.resize(1000, 600)

        self.all_entries = []
        self.current_filter = ("all", None)  # (kind, value) kind: "all" | "status" | "category"

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        outer_layout.addWidget(splitter)

        # Sidebar
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMaximumWidth(220)
        self._build_tree()
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        splitter.addWidget(self.tree)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["File Name", "Size", "Status", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        splitter.addWidget(self.table)

        splitter.setStretchFactor(1, 1)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.clear_btn = QPushButton("Clear History")
        self.refresh_btn.clicked.connect(self.refresh)
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.clear_btn)
        outer_layout.addLayout(btn_row)

        self.refresh()

    def _build_tree(self):
        self.tree.clear()

        all_item = QTreeWidgetItem(["All Downloads"])
        all_item.setData(0, Qt.UserRole, ("all", None))
        self.tree.addTopLevelItem(all_item)

        unfinished_item = QTreeWidgetItem(["Unfinished"])
        unfinished_item.setData(0, Qt.UserRole, ("status", "unfinished"))
        self.tree.addTopLevelItem(unfinished_item)

        finished_item = QTreeWidgetItem(["Finished"])
        finished_item.setData(0, Qt.UserRole, ("status", "completed"))
        self.tree.addTopLevelItem(finished_item)

        categories_root = QTreeWidgetItem(["Categories"])
        categories_root.setData(0, Qt.UserRole, ("all", None))
        self.tree.addTopLevelItem(categories_root)
        for cat in ALL_CATEGORIES:
            cat_item = QTreeWidgetItem([cat])
            cat_item.setData(0, Qt.UserRole, ("category", cat))
            categories_root.addChild(cat_item)

        self.tree.expandAll()

    def on_tree_item_clicked(self, item, _column):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        self.current_filter = data
        self.populate_table()

    def refresh(self):
        self.all_entries = load_history()
        self.populate_table()

    def _filtered_entries(self):
        kind, value = self.current_filter
        if kind == "all":
            return self.all_entries
        if kind == "status":
            if value == "unfinished":
                return [e for e in self.all_entries if e.get("status") not in ("completed",)]
            return [e for e in self.all_entries if e.get("status") == value]
        if kind == "category":
            return [e for e in self.all_entries if e.get("category") == value]
        return self.all_entries

    def populate_table(self):
        entries = self._filtered_entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            size_mb = (entry.get("size_bytes") or 0) / (1024 * 1024)
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get("timestamp", 0)))

            self.table.setItem(row, 0, QTableWidgetItem(entry.get("filename", "")))
            self.table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.2f} MB"))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("status", "")))
            self.table.setItem(row, 3, QTableWidgetItem(date_str))

        self._current_rows = entries

    def on_row_double_clicked(self, index):
        row = index.row()
        entries = getattr(self, "_current_rows", [])
        if row < 0 or row >= len(entries):
            return
        path = entries[row].get("path", "")
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
        clear_history()
        self.refresh()