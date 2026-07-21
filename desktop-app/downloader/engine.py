import os
import time
import asyncio
import aiohttp
import aiofiles
import json
import certifi
import ssl

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class RateLimiter:
    """Shared token-bucket style limiter across all chunk downloads of one engine."""
    def __init__(self, limit_bytes_per_sec=0):
        self.limit = limit_bytes_per_sec  # 0 or None = unlimited
        self.lock = asyncio.Lock()
        self.window_start = time.time()
        self.window_bytes = 0

    async def throttle(self, nbytes):
        if not self.limit or self.limit <= 0:
            return
        async with self.lock:
            now = time.time()
            elapsed = now - self.window_start
            if elapsed >= 1:
                self.window_start = now
                self.window_bytes = 0
                elapsed = 0
            self.window_bytes += nbytes
            if self.window_bytes > self.limit:
                sleep_time = 1 - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                self.window_start = time.time()
                self.window_bytes = 0


class DownloadEngine:
    def __init__(self, url, save_path, num_connections=8, progress_callback=None, speed_limit_kbps=0):
        self.url = url
        self.save_path = save_path
        self.num_connections = num_connections
        self.progress_callback = progress_callback
        self.file_size = 0
        self.supports_range = False
        self.downloaded_bytes = 0
        self.is_paused = False
        self.is_cancelled = False
        self.part_files = []
        self.error = None
        self.rate_limiter = RateLimiter(speed_limit_kbps * 1024 if speed_limit_kbps else 0)

    async def _check_server_support(self, session):
        """Check file size and whether server supports range requests."""
        async with session.head(self.url, allow_redirects=True) as resp:
            self.file_size = int(resp.headers.get("Content-Length", 0))
            accept_ranges = resp.headers.get("Accept-Ranges", "")
            self.supports_range = accept_ranges == "bytes" and self.file_size > 0

    def _get_chunk_ranges(self):
        """Split file size into byte ranges for each connection."""
        chunk_size = self.file_size // self.num_connections
        ranges = []
        for i in range(self.num_connections):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.num_connections - 1 else self.file_size - 1
            ranges.append((start, end))
        return ranges

    async def _download_chunk(self, session, start, end, part_index):
        """Download a single byte-range chunk, resuming if partially done."""
        part_path = f"{self.save_path}.part{part_index}"
        self.part_files.append(part_path)

        existing_bytes = 0
        if os.path.exists(part_path):
            existing_bytes = os.path.getsize(part_path)
            start += existing_bytes

        if start > end:
            return  # already fully downloaded

        headers = {"Range": f"bytes={start}-{end}"}
        async with session.get(self.url, headers=headers) as resp:
            mode = "ab" if existing_bytes else "wb"
            async with aiofiles.open(part_path, mode) as f:
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    if self.is_cancelled:
                        return
                    while self.is_paused:
                        await asyncio.sleep(0.5)
                        if self.is_cancelled:
                            return
                    await f.write(chunk)
                    self.downloaded_bytes += len(chunk)
                    if self.progress_callback:
                        self.progress_callback(self.downloaded_bytes, self.file_size)
                    await self.rate_limiter.throttle(len(chunk))

    async def _download_single(self, session):
        """Fallback: download without ranges (server doesn't support them)."""
        async with session.get(self.url) as resp:
            async with aiofiles.open(self.save_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    if self.is_cancelled:
                        return
                    while self.is_paused:
                        await asyncio.sleep(0.5)
                        if self.is_cancelled:
                            return
                    await f.write(chunk)
                    self.downloaded_bytes += len(chunk)
                    if self.progress_callback:
                        self.progress_callback(self.downloaded_bytes, self.file_size)
                    await self.rate_limiter.throttle(len(chunk))

    def _merge_parts(self):
        """Combine all .partN files into the final file, then delete parts."""
        with open(self.save_path, "wb") as outfile:
            for part_path in self.part_files:
                with open(part_path, "rb") as infile:
                    outfile.write(infile.read())
        for part_path in self.part_files:
            os.remove(part_path)

    def _cleanup_parts(self):
        """Remove leftover .partN files after a failed or cancelled download."""
        for part_path in self.part_files:
            try:
                if os.path.exists(part_path):
                    os.remove(part_path)
            except OSError:
                pass

    async def start(self):
        self.error = None
        connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                await self._check_server_support(session)

                if not self.supports_range:
                    await self._download_single(session)
                    if self.is_cancelled:
                        self._cleanup_parts()
                        if os.path.exists(self.save_path):
                            try:
                                os.remove(self.save_path)
                            except OSError:
                                pass
                    return

                ranges = self._get_chunk_ranges()
                tasks = [
                    self._download_chunk(session, start, end, i)
                    for i, (start, end) in enumerate(ranges)
                ]
                await asyncio.gather(*tasks)

                if self.is_cancelled:
                    self._cleanup_parts()
                    return

                self._merge_parts()
        except Exception as e:
            self.error = str(e)
            self._cleanup_parts()
            raise

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def cancel(self):
        self.is_cancelled = True