import asyncio
from downloader.engine import DownloadEngine

def show_progress(downloaded, total):
    if total > 0:
        percent = (downloaded / total) * 100
        print(f"\rProgress: {percent:.1f}% ({downloaded}/{total} bytes)", end="")

async def main():
    url = "https://proof.ovh.net/files/100Mb.dat"  # test file
    save_path = "test_100MB.bin"

    engine = DownloadEngine(url, save_path, num_connections=8, progress_callback=show_progress)
    await engine.start()
    print("\nDownload complete!")

if __name__ == "__main__":
    asyncio.run(main())