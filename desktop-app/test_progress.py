import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.progress_dialog import ProgressDialog

app = QApplication(sys.argv)

dlg = ProgressDialog("download_test.jpg")

total_size = 5_000_000  # 5 MB fake file
state = {"downloaded": 0}

def fake_progress():
    state["downloaded"] += 250_000  # simulate 250KB per tick
    dlg.update_progress(state["downloaded"], total_size, speed_bytes_per_sec=500_000)
    if state["downloaded"] >= total_size:
        timer.stop()
        dlg.mark_complete()

timer = QTimer()
timer.timeout.connect(fake_progress)
timer.start(300)  # every 300ms

if dlg.exec():
    print("Download finished")
else:
    print("Cancelled, cancelled flag:", dlg.cancelled)