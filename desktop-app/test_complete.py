import sys
from PySide6.QtWidgets import QApplication
from gui.complete_dialog import CompleteDialog

app = QApplication(sys.argv)

dlg = CompleteDialog(
    filename="download_test.jpg",
    save_path=r"C:\Users\amrit\Downloads\MyDownloader\download_test.jpg",
    file_size_bytes=4_770_000
)
dlg.exec()