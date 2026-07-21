from fastapi import FastAPI
from pydantic import BaseModel
from urllib.parse import urlparse, unquote
import asyncio
import os
import sys
import time
import tempfile
import mimetypes
import ssl
import certifi
import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from downloader.engine import DownloadEngine
from downloader import youtube_extractor

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

active_downloads = {}

gui_handler = None
youtube_gui_handler = None

_recent_requests = {}
DEDUPE_WINDOW_SECONDS = 5


class DownloadRequest(BaseModel):
    url: str
    filename: str

class NewDownloadRequest(BaseModel):
    url: str
    filename: str = ""
    referrer: str = ""

class ExtractFormatsRequest(BaseModel):
    url: str
    cookies: str = ""

class NewYoutubeDownloadRequest(BaseModel):
    url: str
    format_selector: str
    is_audio_only: bool = False
    title: str = ""
    cookies: str = ""


def _write_temp_cookiefile(cookies: str):
    """Write extension-supplied cookies (Netscape format) to a temp file for yt-dlp. Returns path or None."""
    if not cookies or not cookies.strip():
        return None
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="mydownloader_cookies_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cookies)
    return path


def _cleanup_cookiefile(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


async def _guess_extension_from_headers(url: str) -> str:
    ext = ".jpg"
    try:
        connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
                guessed = mimetypes.guess_extension(content_type) if content_type else None
                if guessed:
                    ext = guessed
    except Exception:
        pass
    return ext


async def guess_filename(url: str) -> str:
    path = urlparse(url).path
    name = unquote(os.path.basename(path))
    if not name or "." not in name:
        ext = await _guess_extension_from_headers(url)
        name = f"download_{int(time.time())}{ext}"
    return name


async def ensure_extension(filename: str, url: str) -> str:
    filename = filename.strip()
    if not filename:
        return await guess_filename(url)

    base, ext = os.path.splitext(filename)
    if not ext or len(ext) < 2:
        guessed_ext = await _guess_extension_from_headers(url)
        filename = f"{base or f'download_{int(time.time())}'}{guessed_ext}"
    return filename


def unique_path(save_folder: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(save_folder, candidate)):
        candidate = f"{base}_{counter}{ext}"
        counter += 1
    return candidate


@app.get("/")
def read_root():
    return {"status": "IDM Personal server is running"}


@app.post("/download")
async def start_download(req: DownloadRequest):
    save_folder = os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader")
    os.makedirs(save_folder, exist_ok=True)
    save_path = os.path.join(save_folder, req.filename)

    def progress(downloaded, total):
        active_downloads[req.filename] = {"downloaded": downloaded, "total": total, "status": "downloading"}

    engine = DownloadEngine(req.url, save_path, num_connections=8, progress_callback=progress)
    active_downloads[req.filename] = {"downloaded": 0, "total": 0, "status": "starting"}
    asyncio.create_task(run_download(engine, req.filename))
    return {"message": f"Download started for {req.filename}"}


@app.post("/new-download")
async def new_download(req: NewDownloadRequest):
    now = time.time()
    last_seen = _recent_requests.get(req.url)
    if last_seen and (now - last_seen) < DEDUPE_WINDOW_SECONDS:
        return {"status": "duplicate_ignored"}
    _recent_requests[req.url] = now

    if req.filename.strip():
        filename = await ensure_extension(req.filename, req.url)
    else:
        filename = await guess_filename(req.url)

    if gui_handler:
        result = await gui_handler(req.url, filename, req.referrer)
        return result

    save_folder = os.path.join(os.path.expanduser("~"), "Downloads", "MyDownloader")
    os.makedirs(save_folder, exist_ok=True)
    filename = unique_path(save_folder, filename)
    save_path = os.path.join(save_folder, filename)

    def progress(downloaded, total):
        active_downloads[filename] = {"downloaded": downloaded, "total": total, "status": "downloading"}

    engine = DownloadEngine(req.url, save_path, num_connections=8, progress_callback=progress)
    active_downloads[filename] = {"downloaded": 0, "total": 0, "status": "starting"}
    asyncio.create_task(run_download(engine, filename))
    return {"message": f"Download started for {filename}", "filename": filename}


@app.post("/extract-formats")
async def extract_formats(req: ExtractFormatsRequest):
    """List available qualities for a YouTube (or yt-dlp supported) URL."""
    cookiefile = _write_temp_cookiefile(req.cookies)
    try:
        result = await asyncio.to_thread(youtube_extractor.list_formats, req.url, cookiefile)
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _cleanup_cookiefile(cookiefile)


@app.post("/new-youtube-download")
async def new_youtube_download(req: NewYoutubeDownloadRequest):
    now = time.time()
    dedupe_key = f"{req.url}|{req.format_selector}"
    last_seen = _recent_requests.get(dedupe_key)
    if last_seen and (now - last_seen) < DEDUPE_WINDOW_SECONDS:
        return {"status": "duplicate_ignored"}
    _recent_requests[dedupe_key] = now

    if youtube_gui_handler:
        result = await youtube_gui_handler(req.url, req.format_selector, req.is_audio_only, req.title, req.cookies)
        return result

    return {"status": "error", "error": "Desktop app GUI is not connected."}


async def run_download(engine, filename):
    await engine.start()
    active_downloads[filename]["status"] = "completed"


@app.get("/status")
def get_status():
    return active_downloads