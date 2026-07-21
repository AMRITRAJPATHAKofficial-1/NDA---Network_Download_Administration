import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QFileDialog, QCheckBox
)


class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)

        self.saved_settings = None  # set on save

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Default save folder:"))
        folder_row = QHBoxLayout()
        self.folder_field = QLineEdit(current_settings.get("save_folder", ""))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.on_browse)
        folder_row.addWidget(self.folder_field)
        folder_row.addWidget(self.browse_btn)
        layout.addLayout(folder_row)

        layout.addWidget(QLabel("Number of connections per download:"))
        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, 16)
        self.connections_spin.setValue(current_settings.get("num_connections", 8))
        layout.addWidget(self.connections_spin)

        layout.addWidget(QLabel("Speed limit (KB/s, 0 = unlimited):"))
        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(0, 1_000_000)
        self.speed_limit_spin.setSingleStep(100)
        self.speed_limit_spin.setValue(current_settings.get("speed_limit_kbps", 0))
        layout.addWidget(self.speed_limit_spin)

        self.autostart_check = QCheckBox("Start My Downloader automatically when Windows starts")
        self.autostart_check.setChecked(current_settings.get("auto_start_enabled", False))
        layout.addWidget(self.autostart_check)

        self.clipboard_check = QCheckBox("Monitor clipboard for download links")
        self.clipboard_check.setChecked(current_settings.get("clipboard_monitoring_enabled", False))
        layout.addWidget(self.clipboard_check)

        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def on_browse(self):
        current = self.folder_field.text() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Choose default save folder", current)
        if chosen:
            self.folder_field.setText(chosen)

    def on_save(self):
        self.saved_settings = {
            "save_folder": self.folder_field.text().strip() or os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader"),
            "num_connections": self.connections_spin.value(),
            "speed_limit_kbps": self.speed_limit_spin.value(),
            "auto_start_enabled": self.autostart_check.isChecked(),
            "clipboard_monitoring_enabled": self.clipboard_check.isChecked()
        }
        self.accept()