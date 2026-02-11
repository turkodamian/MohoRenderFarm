"""Download and install bundled FFmpeg for Moho Render Farm."""
import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

FFMPEG_URL = "https://github.com/turkodamian/MohoRenderFarm/releases/download/v1.2.0/ffmpeg.zip"
FFMPEG_DIR = Path(__file__).parent / "ffmpeg"
FFMPEG_ZIP = Path(__file__).parent / "ffmpeg.zip"


def download_with_progress(url, dest):
    """Download a file with progress display."""
    print(f"  Downloading from:\n  {url}")
    try:
        response = urllib.request.urlopen(url)
    except urllib.error.URLError as e:
        print(f"  ERROR: Could not connect: {e}")
        return False

    total = int(response.headers.get("Content-Length", 0))
    downloaded = 0
    block_size = 1024 * 64  # 64 KB

    with open(dest, "wb") as f:
        while True:
            chunk = response.read(block_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                print(f"\r  Progress: {pct}% ({mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)
    print()
    return True


def setup_ffmpeg():
    """Download and extract FFmpeg if not already present."""
    if (FFMPEG_DIR / "ffmpeg.exe").exists():
        print("  FFmpeg already installed. Skipping download.")
        return True

    print("  FFmpeg not found. Downloading...")

    if not download_with_progress(FFMPEG_URL, str(FFMPEG_ZIP)):
        return False

    # Extract
    print("  Extracting ffmpeg.zip...")
    try:
        FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(FFMPEG_ZIP), "r") as zf:
            zf.extractall(str(FFMPEG_DIR))
    except (zipfile.BadZipFile, OSError) as e:
        print(f"  ERROR: Failed to extract: {e}")
        return False
    finally:
        # Clean up zip
        if FFMPEG_ZIP.exists():
            FFMPEG_ZIP.unlink()

    # Verify
    if (FFMPEG_DIR / "ffmpeg.exe").exists():
        count = len(list(FFMPEG_DIR.iterdir()))
        print(f"  FFmpeg installed successfully ({count} files)")
        return True
    else:
        print("  ERROR: ffmpeg.exe not found after extraction.")
        return False


if __name__ == "__main__":
    print("=" * 44)
    print("  Moho Render Farm - FFmpeg Setup")
    print("=" * 44)
    print()
    success = setup_ffmpeg()
    sys.exit(0 if success else 1)
