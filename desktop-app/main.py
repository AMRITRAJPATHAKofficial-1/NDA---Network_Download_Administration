import sys
import os
import re
import time
import tempfile
import asyncio
import atexit
import subprocess
import ssl
import certifi
import aiohttp
import uvicorn
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon
import qasync

from gui.download_dialog import DownloadConfirmDialog
from gui.progress_dialog import ProgressDialog
from gui.complete_dialog import CompleteDialog
from gui.error_dialog import ErrorDialog
from gui.settings_dialog import SettingsDialog
from gui.history_dialog import HistoryDialog
from gui.main_window import MainWindow
from downloader.engine import DownloadEngine
from downloader import youtube_extractor
from downloader.youtube_extractor import (
    DownloadController,
    DownloadCancelled,
    DENO_PATH,
    POT_PROVIDER_SERVER_DIR,
)
from downloader.history_manager import load_history, add_history_entry, clear_history
from downloader.categorizer import guess_category
from config.settings_manager import load_settings, save_settings
from utils.autostart import set_autostart_enabled
from utils.clipboard_monitor import ClipboardMonitor

import server.local_api as local_api

_open_dialogs = []       # keeps dialog references alive so Qt doesn't garbage-collect them
_active_downloads = {}   # filename -> progress_dlg, for reopening from tray menu
_reserved_paths = set()  # save_paths currently claimed by an in-progress download
_settings = load_settings()
_main_window = None       # created lazily, kept alive as a singleton
_clipboard_monitor = ClipboardMonitor()
_pot_provider_process = None  # subprocess handle for the vendored PO Token HTTP server


def _kill_stale_pot_provider():
    """Kill any leftover deno.exe processes from previous runs that are still
    holding port 4416 — prevents new pot-provider starts from silently failing
    with EADDRINUSE after an earlier session wasn't shut down cleanly."""
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "deno.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def start_pot_provider():
    """Launch the vendored bgutil PO-Token HTTP server (desktop-app/pot-provider)
    as a background subprocess using the vendored Deno binary, so the project
    needs no system-wide Deno/Node install and no manual second terminal.
    Silently does nothing if either piece hasn't been set up yet — yt-dlp will
    just fall back to whatever's on PATH / limited formats, same as before."""
    global _pot_provider_process
    _kill_stale_pot_provider()

    node_modules_dir = os.path.join(POT_PROVIDER_SERVER_DIR, "node_modules")
    entry_script = os.path.join(POT_PROVIDER_SERVER_DIR, "src", "main.ts")

    if not (os.path.exists(DENO_PATH) and os.path.exists(node_modules_dir) and os.path.exists(entry_script)):
        print("[pot-provider] Vendored deno/pot-provider not found — skipping (falls back to system PATH / 360p-only).")
        return

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "pot_provider.log")

    try:
        log_file = open(log_path, "a", encoding="utf-8")
        _pot_provider_process = subprocess.Popen(
            [DENO_PATH, "run", "--allow-env", "--allow-net", "--allow-ffi=.", "--allow-read=.", "../src/main.ts"],
            cwd=node_modules_dir,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        print(f"[pot-provider] Started (pid {_pot_provider_process.pid}) — logs: {log_path}")
    except Exception as e:
        print(f"[pot-provider] Failed to start: {e}")
        _pot_provider_process = None


def stop_pot_provider():
    global _pot_provider_process
    if _pot_provider_process is not None and _pot_provider_process.poll() is None:
        try:
            _pot_provider_process.terminate()
            _pot_provider_process.wait(timeout=5)
        except Exception:
            try:
                _pot_provider_process.kill()
            except Exception:
                pass
        print("[pot-provider] Stopped.")


def cleanup_orphaned_parts(save_folder):
    """Remove leftover .partN files from crashed/interrupted downloads on startup."""
    if not os.path.exists(save_folder):
        return
    removed = 0
    for root, _dirs, files in os.walk(save_folder):
        for fname in files:
            if ".part" in fname:
                suffix = fname.rsplit(".part", 1)[-1]
                if suffix.isdigit():
                    try:
                        os.remove(os.path.join(root, fname))
                        removed += 1
                    except OSError:
                        pass
    if removed:
        print(f"[startup cleanup] Removed {removed} orphaned .part file(s)")


async def get_remote_file_size(url):
    """Quick HEAD request to check file size before showing the confirm dialog."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return int(resp.headers.get("Content-Length", 0))
    except Exception:
        return 0


def guess_filename_from_clipboard_url(url):
    """Guess a reasonable filename for a URL detected via clipboard monitoring."""
    from urllib.parse import urlparse, unquote
    import time as _time
    path = urlparse(url).path
    name = unquote(os.path.basename(path))
    if not name or "." not in name:
        name = f"download_{int(_time.time())}.bin"
    return name


def safe_filename(name):
    """Strip characters Windows won't allow in filenames."""
    return "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "video"


_ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(text):
    """Remove ANSI color codes (e.g. from yt-dlp's internal error strings) so
    they don't show up as garbled [0;31m...[0m text in dialogs/popups."""
    return _ANSI_ESCAPE.sub('', text)

YT_DLP_DOMAINS = ("youtube.com", "youtu.be", "instagram.com", "x.com", "twitter.com")


def is_ytdlp_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname or ""
        host = host.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in YT_DLP_DOMAINS)
    except Exception:
        return False
    
async def show_dialog_async(dialog):
    """Show a Qt dialog non-blockingly and await its result."""
    loop = asyncio.get_event_loop()
    future = loop.create_future()

    def on_finished(result):
        if not future.done():
            future.set_result(result)

    dialog.finished.connect(on_finished)
    dialog.show()
    return await future


def unique_path_full(path):
    folder = os.path.dirname(path)
    filename = os.path.basename(path)
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}_{counter}{ext}"
        counter += 1
    return os.path.join(folder, candidate)


def reserve_unique_path(path):
    """Like unique_path_full, but also avoids paths claimed by other downloads
    that are still in progress (haven't created their final file yet)."""
    candidate = unique_path_full(path)
    while candidate in _reserved_paths:
        folder = os.path.dirname(candidate)
        filename = os.path.basename(candidate)
        base, ext = os.path.splitext(filename)
        candidate = unique_path_full(os.path.join(folder, f"{base}_r{ext}"))
    _reserved_paths.add(candidate)
    return candidate


def release_reserved_path(path):
    _reserved_paths.discard(path)


async def handle_new_download(url, suggested_filename, referrer=""):
    save_folder = _settings.get("save_folder") or os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader")
    os.makedirs(save_folder, exist_ok=True)

    confirm_dlg = DownloadConfirmDialog(url, suggested_filename, save_folder)

    file_size = await get_remote_file_size(url)
    confirm_dlg.set_file_size(file_size)

    await show_dialog_async(confirm_dlg)

    if confirm_dlg.result_action != "start":
        return {"status": confirm_dlg.result_action or "cancelled"}

    save_path = reserve_unique_path(confirm_dlg.final_save_path)
    filename = os.path.basename(save_path)
    category = confirm_dlg.category
    num_connections = _settings.get("num_connections", 8)
    speed_limit_kbps = _settings.get("speed_limit_kbps", 0)

    try:
        while True:  # allows retry after failure
            progress_dlg = ProgressDialog(filename)
            progress_dlg.show()
            _open_dialogs.append(progress_dlg)
            _active_downloads[filename] = progress_dlg

            download_start = time.time()
            state = {"last_downloaded": 0, "last_time": download_start}
            main_loop = asyncio.get_event_loop()  # capture the main/GUI thread's event loop

            def progress_cb(downloaded, total):
                now = time.time()
                elapsed = now - state["last_time"]
                speed = (downloaded - state["last_downloaded"]) / elapsed if elapsed > 0 else 0
                total_elapsed = now - download_start
                avg_speed = downloaded / total_elapsed if total_elapsed > 0 else 0
                state["last_downloaded"] = downloaded
                state["last_time"] = now

                def _update_ui():
                    progress_dlg.update_progress(
                        downloaded, total,
                        speed_bytes_per_sec=speed,
                        avg_speed_bytes_per_sec=avg_speed
                    )

                main_loop.call_soon_threadsafe(_update_ui)

            engine = DownloadEngine(
                url, save_path,
                num_connections=num_connections,
                progress_callback=progress_cb,
                speed_limit_kbps=speed_limit_kbps
            )

            progress_dlg.on_pause_toggle = lambda paused: engine.resume() if not paused else engine.pause()
            progress_dlg.on_cancel_requested = engine.cancel

            try:
                await engine.start()
            except Exception as e:
                clean_error = strip_ansi(str(e))
                progress_dlg.close()
                if progress_dlg in _open_dialogs:
                    _open_dialogs.remove(progress_dlg)
                _active_downloads.pop(filename, None)

                error_dlg = ErrorDialog(filename, url, clean_error)
                _open_dialogs.append(error_dlg)
                await show_dialog_async(error_dlg)
                if error_dlg in _open_dialogs:
                    _open_dialogs.remove(error_dlg)

                if error_dlg.result_action == "retry":
                    continue

                add_history_entry(filename, save_path, 0, "failed", url, category)
                return {"status": "failed", "error": clean_error}

            if progress_dlg.cancelled:
                if progress_dlg in _open_dialogs:
                    _open_dialogs.remove(progress_dlg)
                _active_downloads.pop(filename, None)
                add_history_entry(filename, save_path, 0, "cancelled", url, category)
                return {"status": "cancelled"}

            progress_dlg.mark_complete()
            _active_downloads.pop(filename, None)
            break

        file_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
        add_history_entry(filename, save_path, file_size, "completed", url, category)

        complete_dlg = CompleteDialog(filename, save_path, file_size)
        complete_dlg.show()
        _open_dialogs.append(complete_dlg)

        def cleanup(_=None):
            if progress_dlg in _open_dialogs:
                _open_dialogs.remove(progress_dlg)
            if complete_dlg in _open_dialogs:
                _open_dialogs.remove(complete_dlg)

        complete_dlg.finished.connect(cleanup)

        return {"status": "completed", "filename": filename, "path": save_path}
    finally:
        release_reserved_path(save_path)


async def handle_new_youtube_download(url, format_selector, is_audio_only, title, cookies=""):
    """Called by /new-youtube-download once a quality/format has already been chosen."""
    save_folder = _settings.get("save_folder") or os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader")
    os.makedirs(save_folder, exist_ok=True)

    ext = "mp3" if is_audio_only else "mp4"
    clean_title = safe_filename(title or "video")
    suggested_filename = f"{clean_title}.{ext}"

    confirm_dlg = DownloadConfirmDialog(url, suggested_filename, save_folder)
    confirm_dlg.set_file_size(0)  # exact size unknown until download starts

    await show_dialog_async(confirm_dlg)

    if confirm_dlg.result_action != "start":
        return {"status": confirm_dlg.result_action or "cancelled"}

    save_path = reserve_unique_path(confirm_dlg.final_save_path)
    filename = os.path.basename(save_path)
    category = confirm_dlg.category

    try:
        progress_dlg = ProgressDialog(filename)
        progress_dlg.show()
        _open_dialogs.append(progress_dlg)
        _active_downloads[filename] = progress_dlg

        controller = DownloadController()
        progress_dlg.on_pause_toggle = lambda paused: controller.pause() if paused else controller.resume()
        progress_dlg.on_cancel_requested = controller.cancel

        download_start = time.time()
        state = {"last_downloaded": 0, "last_time": download_start}
        main_loop = asyncio.get_event_loop()  # capture main/GUI thread's loop for thread-safe UI updates

        def progress_cb(downloaded, total):
            now = time.time()
            elapsed = now - state["last_time"]
            speed = (downloaded - state["last_downloaded"]) / elapsed if elapsed > 0 else 0
            total_elapsed = now - download_start
            avg_speed = downloaded / total_elapsed if total_elapsed > 0 else 0
            state["last_downloaded"] = downloaded
            state["last_time"] = now

            def _update_ui():
                progress_dlg.update_progress(
                downloaded, total,
                speed_bytes_per_sec=speed,
                avg_speed_bytes_per_sec=avg_speed
                )

            main_loop.call_soon_threadsafe(_update_ui)

        try:
            cookiefile = None
            if cookies and cookies.strip():
                fd, cookiefile = tempfile.mkstemp(suffix=".txt", prefix="mydownloader_cookies_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(cookies)

            try:
                num_connections = _settings.get("num_connections", 8)
                final_path = await asyncio.to_thread(
                    youtube_extractor.download,
                    url, format_selector, save_path, is_audio_only, progress_cb, controller, cookiefile, num_connections
                )
            finally:
                if cookiefile and os.path.exists(cookiefile):
                    try:
                        os.remove(cookiefile)
                    except OSError:
                        pass
        except DownloadCancelled:
            progress_dlg.close()
            if progress_dlg in _open_dialogs:
                _open_dialogs.remove(progress_dlg)
            _active_downloads.pop(filename, None)
            add_history_entry(filename, save_path, 0, "cancelled", url, category)
            return {"status": "cancelled"}
        except Exception as e:
            clean_error = strip_ansi(str(e))
            progress_dlg.close()
            if progress_dlg in _open_dialogs:
                _open_dialogs.remove(progress_dlg)
            _active_downloads.pop(filename, None)

            error_dlg = ErrorDialog(filename, url, clean_error)
            _open_dialogs.append(error_dlg)
            await show_dialog_async(error_dlg)
            if error_dlg in _open_dialogs:
                _open_dialogs.remove(error_dlg)

            add_history_entry(filename, save_path, 0, "failed", url, category)
            return {"status": "failed", "error": clean_error}

        progress_dlg.mark_complete()
        _active_downloads.pop(filename, None)

        final_filename = os.path.basename(final_path)
        file_size = os.path.getsize(final_path) if os.path.exists(final_path) else 0
        add_history_entry(final_filename, final_path, file_size, "completed", url, category)

        complete_dlg = CompleteDialog(final_filename, final_path, file_size)
        complete_dlg.show()
        _open_dialogs.append(complete_dlg)

        def cleanup(_=None):
            if progress_dlg in _open_dialogs:
                _open_dialogs.remove(progress_dlg)
            if complete_dlg in _open_dialogs:
                _open_dialogs.remove(complete_dlg)

        complete_dlg.finished.connect(cleanup)

        return {"status": "completed", "filename": final_filename, "path": final_path}
    finally:
        release_reserved_path(save_path)

async def handle_clipboard_ytdlp_link(url):
    """Clipboard monitor caught a YouTube/Instagram/X link — extract formats first,
    then reuse the normal YouTube download flow with the best available quality."""
    try:
        info = await asyncio.to_thread(youtube_extractor.list_formats, url)
    except Exception as e:
        QMessageBox.warning(
            None, "Couldn't extract video",
            f"This link couldn't be processed:\n\n{url}\n\nError: {e}"
        )
        return

    video_options = info.get("video_options", [])
    if not video_options:
        QMessageBox.warning(None, "No video found", f"No downloadable video found at:\n\n{url}")
        return

    # Best available quality by default for clipboard-triggered downloads
    best = video_options[0]
    await handle_new_youtube_download(url, best["format_selector"], False, info.get("title", ""))

def on_clipboard_link_detected(url):
    reply = QMessageBox.question(
        None, "Download link detected?",
        f"Found this link on your clipboard:\n\n{url}\n\nDownload it with Network Download Administration?",
        QMessageBox.Yes | QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return

    if is_ytdlp_url(url):
        asyncio.ensure_future(handle_clipboard_ytdlp_link(url))
    else:
        filename = guess_filename_from_clipboard_url(url)
        asyncio.ensure_future(handle_new_download(url, filename, ""))


def apply_clipboard_monitor_setting():
    if _settings.get("clipboard_monitoring_enabled", False):
        _clipboard_monitor.start()
    else:
        _clipboard_monitor.stop()


def open_settings_dialog():
    global _settings
    dlg = SettingsDialog(_settings)
    _open_dialogs.append(dlg)

    def on_finished(_=None):
        global _settings
        if dlg.saved_settings:
            _settings = dlg.saved_settings
            save_settings(_settings)
            set_autostart_enabled(_settings.get("auto_start_enabled", False))
            apply_clipboard_monitor_setting()
        if dlg in _open_dialogs:
            _open_dialogs.remove(dlg)

    dlg.finished.connect(on_finished)
    dlg.show()


def open_history_dialog():
    entries = load_history()
    dlg = HistoryDialog(entries, on_clear=clear_history)
    _open_dialogs.append(dlg)

    def on_finished(_=None):
        if dlg in _open_dialogs:
            _open_dialogs.remove(dlg)

    dlg.finished.connect(on_finished)
    dlg.show()


def open_main_window():
    global _main_window
    if _main_window is None:
        _main_window = MainWindow()
    _main_window.refresh()
    _main_window.show()
    _main_window.raise_()
    _main_window.activateWindow()


def build_tray_icon(app):
    tray = QSystemTrayIcon(app)
    icon = app.style().standardIcon(app.style().StandardPixmap.SP_ArrowDown)
    tray.setIcon(icon)
    tray.setToolTip("Network Download Administration")

    menu = QMenu()
    open_action = menu.addAction("Open Network Download Administration")
    active_menu = menu.addMenu("Active Downloads")
    menu.addSeparator()
    history_action = menu.addAction("Download History")
    settings_action = menu.addAction("Settings")
    menu.addSeparator()
    quit_action = menu.addAction("Quit")

    def refresh_active_menu():
        active_menu.clear()
        if not _active_downloads:
            empty = active_menu.addAction("(none)")
            empty.setEnabled(False)
            return
        for filename, dlg in list(_active_downloads.items()):
            label = f"{filename} ({'Paused' if dlg.is_paused else 'Downloading'})"
            action = active_menu.addAction(label)
            action.triggered.connect(lambda checked=False, d=dlg: (d.show(), d.raise_(), d.activateWindow()))

    menu.aboutToShow.connect(refresh_active_menu)

    open_action.triggered.connect(open_main_window)
    history_action.triggered.connect(open_history_dialog)
    settings_action.triggered.connect(open_settings_dialog)
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: open_main_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()
    return tray


async def run_server():
    local_api.gui_handler = handle_new_download
    local_api.youtube_gui_handler = handle_new_youtube_download
    config = uvicorn.Config(local_api.app, host="127.0.0.1", port=5000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    save_folder = _settings.get("save_folder")
    cleanup_orphaned_parts(save_folder)

    start_pot_provider()
    atexit.register(stop_pot_provider)  # safety net for any exit path

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    set_autostart_enabled(_settings.get("auto_start_enabled", False))

    tray = build_tray_icon(app)

    _clipboard_monitor.link_detected.connect(on_clipboard_link_detected)
    apply_clipboard_monitor_setting()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        try:
            loop.run_until_complete(run_server())
        except KeyboardInterrupt:
            pass
        finally:
            stop_pot_provider()