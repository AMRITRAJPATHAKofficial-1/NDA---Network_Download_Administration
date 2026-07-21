import asyncio
from downloader.engine import DownloadEngine

def show_progress(downloaded, total):
    if total > 0:
        percent = (downloaded / total) * 100
        print(f"\rProgress: {percent:.1f}% ({downloaded}/{total} bytes)", end="")

async def main():
    url = "https://proof.ovh.net/files/100Mb.dat"
    save_path = "test_pause_100MB.bin"

    engine = DownloadEngine(url, save_path, num_connections=8, progress_callback=show_progress)

    task = asyncio.create_task(engine.start())

    await asyncio.sleep(3)
    print("\n\n--- PAUSING ---\n")
    engine.pause()

    await asyncio.sleep(5)
    print("--- RESUMING ---\n")
    engine.resume()

    await task
    print("\nDownload complete!")

if __name__ == "__main__":
    asyncio.run(main())