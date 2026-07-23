import os
import time
import threading
import yt_dlp

FFMPEG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg", "ffmpeg.exe")
DENO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deno", "deno.exe")
POT_PROVIDER_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pot-provider", "server")

DIAGNOSTIC_MODE = False  # set False once everything's confirmed working


class DownloadCancelled(Exception):
    pass


class DownloadController:
    """Lets the GUI pause/resume/cancel a yt-dlp download in progress."""
    def __init__(self):
        self.paused = threading.Event()
        self.cancelled = threading.Event()

    def pause(self):
        self.paused.set()

    def resume(self):
        self.paused.clear()

    def cancel(self):
        self.cancelled.set()
        self.paused.clear()


def _js_runtimes_opt():
    """Point yt-dlp at the vendored Deno binary if present, else fall back to system PATH."""
    if os.path.exists(DENO_PATH):
        return {"deno": {"path": DENO_PATH}}
    return {"deno": {}}


def _extractor_args():
    return {"youtube": {"player_client": ["web", "web_safari", "android", "ios", "mweb"]}}


def list_formats(url, cookiefile=None):
    """Return video title + curated quality options for the quality-picker."""
    ydl_opts = {
        "quiet": not DIAGNOSTIC_MODE,
        "verbose": DIAGNOSTIC_MODE,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": _extractor_args(),
        "js_runtimes": _js_runtimes_opt(),
    }
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title", "video")
    duration = info.get("duration")  # seconds, used for size estimation fallback
    formats = info.get("formats", [])

    seen_heights = set()
    video_options = []
    for f in sorted(formats, key=lambda x: (x.get("height") or 0), reverse=True):
        height = f.get("height")
        vcodec = f.get("vcodec")
        if not height or height < 100 or vcodec == "none" or height in seen_heights:
            continue
        seen_heights.add(height)
        ext = f.get("ext", "mp4")

        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        estimated = False
        if not filesize:
            tbr = f.get("tbr")  # bitrate in kbps
            if tbr and duration:
                filesize = int((tbr * 1000 / 8) * duration)  # kbps -> bytes over duration
                estimated = True

        if filesize:
            size_label = f"{filesize / (1024*1024):.1f} MB" + (" (est.)" if estimated else "")
        else:
            size_label = "size unknown"

        video_options.append({
            "label": f"{height}p ({ext}) - {size_label}",
            "format_selector": f"{f['format_id']}+bestaudio/best",
            "height": height,
        })

    audio_option = {
        "label": "Audio only (best quality, mp3)",
        "format_selector": "bestaudio/best",
    }

    return {"title": title, "video_options": video_options, "audio_option": audio_option}


def download(url, format_selector, save_path, is_audio_only=False, progress_callback=None,
             controller=None, cookiefile=None, num_connections=8):
    """Blocking download — always call via asyncio.to_thread() from async code."""
    save_dir = os.path.dirname(save_path)
    base_name = os.path.splitext(os.path.basename(save_path))[0]

    def hook(d):
        if controller is not None:
            if controller.cancelled.is_set():
                raise DownloadCancelled("Cancelled by user")
            while controller.paused.is_set():
                if controller.cancelled.is_set():
                    raise DownloadCancelled("Cancelled by user")
                time.sleep(0.5)

        if progress_callback is None:
            return
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            progress_callback(downloaded, total)
        elif d["status"] == "finished":
            total = d.get("total_bytes") or d.get("downloaded_bytes", 0)
            progress_callback(total, total)

    ydl_opts = {
        "format": format_selector,
        "outtmpl": os.path.join(save_dir, f"{base_name}.%(ext)s"),
        "progress_hooks": [hook],
        "noplaylist": True,
        "quiet": not DIAGNOSTIC_MODE,
        "verbose": DIAGNOSTIC_MODE,
        "extractor_args": _extractor_args(),
        "js_runtimes": _js_runtimes_opt(),
        # --- speed fixes: parallel chunked downloading, IDM-style ---
        "concurrent_fragment_downloads": num_connections,
        "http_chunk_size": 10 * 1024 * 1024,  # 10MB chunks, enables range-request parallelism
    }
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    if os.path.exists(FFMPEG_PATH):
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    if is_audio_only:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        final_path = ydl.prepare_filename(info)
        if is_audio_only:
            final_path = os.path.splitext(final_path)[0] + ".mp3"
        elif not final_path.endswith(".mp4"):
            candidate = os.path.splitext(final_path)[0] + ".mp4"
            if os.path.exists(candidate):
                final_path = candidate

    return final_path