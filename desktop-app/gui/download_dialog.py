import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt

from downloader.categorizer import ALL_CATEGORIES, guess_category


class DownloadConfirmDialog(QDialog):
    def __init__(self, url, suggested_filename, save_folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Download")
        self.setMinimumWidth(520)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.url = url
        self.save_folder = save_folder
        self.suggested_filename = suggested_filename
        self.result_action = None  # "start" | "later" | "cancelled"
        self.category = guess_category(suggested_filename)
        self.final_save_path = os.path.join(save_folder, self.category, suggested_filename)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("URL:"))
        self.url_field = QLineEdit(url)
        self.url_field.setReadOnly(True)
        layout.addWidget(self.url_field)

        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(ALL_CATEGORIES)
        self.category_combo.setCurrentText(self.category)
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        layout.addWidget(self.category_combo)

        layout.addWidget(QLabel("Save to:"))
        save_row = QHBoxLayout()
        self.save_path_field = QLineEdit(self.final_save_path)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.on_browse)
        save_row.addWidget(self.save_path_field)
        save_row.addWidget(self.browse_btn)
        layout.addLayout(save_row)

        self.size_label = QLabel("File size: checking...")
        layout.addWidget(self.size_label)

        btn_row = QHBoxLayout()
        self.later_btn = QPushButton("Download Later")
        self.cancel_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Start Download")
        self.later_btn.clicked.connect(self.on_later)
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.start_btn.clicked.connect(self.on_start)
        btn_row.addWidget(self.later_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.start_btn)
        layout.addLayout(btn_row)

    def on_category_changed(self, new_category):
        self.category = new_category
        filename = os.path.basename(self.save_path_field.text() or self.suggested_filename)
        self.final_save_path = os.path.join(self.save_folder, new_category, filename)
        self.save_path_field.setText(self.final_save_path)

    def set_file_size(self, size_bytes):
        if size_bytes and size_bytes > 0:
            mb = size_bytes / (1024 * 1024)
            self.size_label.setText(f"File size: {mb:.2f} MB")
        else:
            self.size_label.setText("File size: unknown")

    def on_browse(self):
        current_path = self.save_path_field.text()
        current_dir = os.path.dirname(current_path) or self.save_folder
        current_name = os.path.basename(current_path)

        chosen_path, _ = QFileDialog.getSaveFileName(
            self, "Choose save location",
            os.path.join(current_dir, current_name)
        )
        if chosen_path:
            self.save_path_field.setText(chosen_path)

    def _sync_final_path(self):
        path = self.save_path_field.text().strip()
        if path:
            self.final_save_path = path
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)

    def on_start(self):
        self._sync_final_path()
        self.result_action = "start"
        self.accept()

    def on_later(self):
        self.result_action = "later"
        self.reject()

    def on_cancel(self):
        self.result_action = "cancelled"
        self.reject()