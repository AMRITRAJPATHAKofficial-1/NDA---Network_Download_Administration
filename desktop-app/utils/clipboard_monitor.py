import re
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

URL_REGEX = re.compile(r'^https?://\S+$')


class ClipboardMonitor(QObject):
    link_detected = Signal(str)

    def __init__(self, interval_ms=1500, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_clipboard)
        self.interval_ms = interval_ms
        self.last_text = ""
        self._running = False

    def start(self):
        if self._running:
            return
        self.last_text = QApplication.clipboard().text()  # baseline, don't prompt for what's already there
        self.timer.start(self.interval_ms)
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False

    def _check_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if not text or text == self.last_text:
            return
        self.last_text = text
        if URL_REGEX.match(text):
            self.link_detected.emit(text)