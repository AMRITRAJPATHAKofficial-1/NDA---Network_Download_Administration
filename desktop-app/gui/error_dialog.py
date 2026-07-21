from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt


class ErrorDialog(QDialog):
    def __init__(self, filename, url, error_message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Failed")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.result_action = None  # "retry" or "close"

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Failed to download: {filename}"))
        layout.addWidget(QLabel(f"URL: {url}"))

        error_label = QLabel(f"Error: {error_message}")
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        btn_row = QHBoxLayout()
        retry_btn = QPushButton("Retry")
        close_btn = QPushButton("Close")

        retry_btn.clicked.connect(self.on_retry)
        close_btn.clicked.connect(self.on_close)

        btn_row.addStretch()
        btn_row.addWidget(retry_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def on_retry(self):
        self.result_action = "retry"
        self.accept()

    def on_close(self):
        self.result_action = "close"
        self.accept()