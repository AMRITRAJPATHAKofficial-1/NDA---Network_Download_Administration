import os
import sys
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt


class CompleteDialog(QDialog):
    def __init__(self, filename, save_path, file_size, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Complete")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.filename = filename
        self.save_path = save_path
        self.file_size = file_size

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Download complete: {filename}"))

        size_mb = file_size / (1024 * 1024) if file_size else 0
        layout.addWidget(QLabel(f"Size: {size_mb:.2f} MB"))
        layout.addWidget(QLabel(f"Saved to: {save_path}"))

        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("Open")
        self.open_folder_btn = QPushButton("Open Folder")
        self.close_btn = QPushButton("Close")

        self.open_btn.clicked.connect(self.on_open_file)
        self.open_folder_btn.clicked.connect(self.on_open_folder)
        self.close_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def on_open_file(self):
        try:
            if sys.platform == "win32":
                os.startfile(self.save_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", self.save_path])
            else:
                subprocess.run(["xdg-open", self.save_path])
        except Exception as e:
            print(f"Failed to open file: {e}")

    def on_open_folder(self):
        folder = os.path.dirname(self.save_path)
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(self.save_path)])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", self.save_path])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            print(f"Failed to open folder: {e}")