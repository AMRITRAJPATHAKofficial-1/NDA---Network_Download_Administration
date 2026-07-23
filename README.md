# Network Download Administration (NDA)

A personal IDM-style download manager: a Chrome extension, a local FastAPI server, and a PySide6 desktop app working together to handle direct file downloads and YouTube/Instagram/X video downloads with full quality selection.

## Features

- Segmented, multi-connection direct file downloads (pause/resume/cancel)
- YouTube, Instagram, and X video downloads via yt-dlp, with full quality ladder (144p–2160p)
- Right-click "Download with My Downloader" context menu in Chrome
- Floating in-page download button on video sites
- Download categories (Video, Music, Pictures, Documents, Compressed, Programs, Other)
- Download history with filtering (All / Unfinished / Finished / by Category)
- System tray icon with active downloads menu
- Clipboard link monitoring (optional)
- Settings: save folder, connection count, speed limit

## Architecture

- **browser-extension/** — Chrome extension (Manifest V3): intercepts downloads, right-click menu, popup UI
- **desktop-app/server/** — FastAPI server (127.0.0.1:5000): receives requests from the extension
- **desktop-app/gui/** — PySide6 dialogs and main window
- **desktop-app/downloader/** — download engine (direct downloads) and yt-dlp wrapper (YouTube/Instagram/X)

## Setup

### Prerequisites
- Python 3.11+
- Google Chrome
- [Deno](https://deno.land/) (for YouTube PO-token support)
- ffmpeg (for merging/audio extraction)

### Install
```bash
cd desktop-app
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```

Place `ffmpeg.exe` inside `desktop-app/ffmpeg/` and `deno.exe` inside `desktop-app/deno/`.

Clone the PO-token provider (required for full YouTube quality support):
```bash
git clone --single-branch --branch 1.3.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git desktop-app/pot-provider
cd desktop-app/pot-provider/server
../../deno/deno.exe install --allow-scripts=npm:canvas --frozen
```

### Run
```bash
cd desktop-app
python main.py
```

Then load the extension in Chrome:
1. Go to `chrome://extensions`
2. Enable Developer Mode
3. Click "Load unpacked" → select the `browser-extension/` folder

## Notes

- This project is for personal/educational use.
- Downloading copyrighted content you don't have rights to may violate the terms of service of the source platform (YouTube, Instagram, X) and applicable law — use responsibly.