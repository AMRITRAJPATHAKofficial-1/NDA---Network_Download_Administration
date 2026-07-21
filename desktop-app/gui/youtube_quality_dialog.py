from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QScrollArea, QWidget
)
from PySide6.QtCore import Qt


class YoutubeQualityDialog(QDialog):
    def __init__(self, title, video_options, audio_option, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Quality")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.result_action = None       # "start" | "cancelled"
        self.selected_format_selector = None
        self.selected_is_audio_only = False

        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        layout.addWidget(QLabel("Select quality:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.button_group = QButtonGroup(self)

        for i, opt in enumerate(video_options):
            rb = QRadioButton(opt["label"])
            rb.setProperty("format_selector", opt["format_selector"])
            rb.setProperty("is_audio_only", False)
            if i == 0:
                rb.setChecked(True)
            self.button_group.addButton(rb)
            scroll_layout.addWidget(rb)

        audio_rb = QRadioButton(audio_option["label"])
        audio_rb.setProperty("format_selector", audio_option["format_selector"])
        audio_rb.setProperty("is_audio_only", True)
        self.button_group.addButton(audio_rb)
        scroll_layout.addWidget(audio_rb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        scroll.setMinimumHeight(220)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.download_btn = QPushButton("Download")
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.download_btn.clicked.connect(self.on_download)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.download_btn)
        layout.addLayout(btn_row)

    def on_download(self):
        selected = self.button_group.checkedButton()
        if not selected:
            return
        self.selected_format_selector = selected.property("format_selector")
        self.selected_is_audio_only = selected.property("is_audio_only")
        self.result_action = "start"
        self.accept()

    def on_cancel(self):
        self.result_action = "cancelled"
        self.reject()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.result_action = "cancelled"