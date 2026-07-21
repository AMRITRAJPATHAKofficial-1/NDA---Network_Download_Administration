import os

CATEGORY_EXTENSIONS = {
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"},
    "Music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Pictures": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".odt"},
    "Compressed": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Programs": {".exe", ".msi", ".dmg", ".apk", ".deb", ".appimage"},
}

ALL_CATEGORIES = ["Video", "Music", "Pictures", "Documents", "Compressed", "Programs", "Other"]


def guess_category(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "Other"