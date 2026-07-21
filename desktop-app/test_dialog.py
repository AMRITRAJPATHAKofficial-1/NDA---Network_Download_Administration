import sys
from PySide6.QtWidgets import QApplication
from gui.download_dialog import DownloadConfirmDialog

app = QApplication(sys.argv)
dlg = DownloadConfirmDialog(
    url="https://plus.unsplash.com/premium_photo-example.jpg",
    suggested_filename="download_test.jpg",
    save_folder=r"C:\Users\amrit\Downloads\MyDownloader"
)
dlg.set_file_size(2_500_000)

if dlg.exec():
    print("Action:", dlg.result_action)
    print("Save path:", dlg.final_save_path)
else:
    print("Cancelled")