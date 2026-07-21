from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
)
from PySide6.QtCore import Qt


class ProgressDialog(QDialog):
    def __init__(self, filename, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloading...")
        self.setMinimumWidth(420)

        # Enable native minimize button + close button in the title bar
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.cancelled = False
        self.is_paused = False

        # main.py sets these after creating the engine
        self.on_pause_toggle = None      # callable(is_paused: bool)
        self.on_cancel_requested = None  # callable()

        layout = QVBoxLayout(self)

        self.filename_label = QLabel(filename)
        layout.addWidget(self.filename_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        info_row = QHBoxLayout()
        self.size_label = QLabel("0 MB / 0 MB")
        self.speed_label = QLabel("0 KB/s")
        self.eta_label = QLabel("ETA: --")
        info_row.addWidget(self.size_label)
        info_row.addWidget(self.speed_label)
        info_row.addWidget(self.eta_label)
        layout.addLayout(info_row)

        avg_row = QHBoxLayout()
        self.avg_speed_label = QLabel("Avg: 0.00 MB/s")
        self.avg_eta_label = QLabel("Avg ETA: --")
        avg_row.addWidget(self.avg_speed_label)
        avg_row.addWidget(self.avg_eta_label)
        layout.addLayout(avg_row)

        btn_row = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.cancel_btn = QPushButton("Cancel")
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def on_pause_clicked(self):
        self.is_paused = not self.is_paused
        self.pause_btn.setText("Resume" if self.is_paused else "Pause")
        if self.on_pause_toggle:
            self.on_pause_toggle(self.is_paused)

    def update_progress(self, downloaded_bytes, total_bytes,
                         speed_bytes_per_sec=0, avg_speed_bytes_per_sec=0):
        if total_bytes > 0:
            percent = int((downloaded_bytes / total_bytes) * 100)
            self.progress_bar.setValue(percent)

        downloaded_mb = downloaded_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024) if total_bytes else 0
        self.size_label.setText(f"{downloaded_mb:.2f} MB / {total_mb:.2f} MB")

        speed_kb = speed_bytes_per_sec / 1024
        self.speed_label.setText(f"{speed_kb:.1f} KB/s")

        if speed_bytes_per_sec > 0 and total_bytes > 0:
            remaining = total_bytes - downloaded_bytes
            eta = remaining / speed_bytes_per_sec
            self.eta_label.setText(f"ETA: {int(eta)}s")
        else:
            self.eta_label.setText("ETA: --")

        avg_mb = avg_speed_bytes_per_sec / (1024 * 1024)
        self.avg_speed_label.setText(f"Avg: {avg_mb:.2f} MB/s")

        if avg_speed_bytes_per_sec > 0 and total_bytes > 0:
            remaining = total_bytes - downloaded_bytes
            avg_eta = remaining / avg_speed_bytes_per_sec
            self.avg_eta_label.setText(f"Avg ETA: {int(avg_eta)}s")
        else:
            self.avg_eta_label.setText("Avg ETA: --")

    def mark_complete(self):
        self.progress_bar.setValue(100)
        self.accept()

    def on_cancel(self):
        self.cancelled = True
        if self.on_cancel_requested:
            self.on_cancel_requested()
        self.reject()

    def closeEvent(self, event):
        # Clicking the title bar's X hides it to the tray instead of cancelling
        event.ignore()
        self.hide()