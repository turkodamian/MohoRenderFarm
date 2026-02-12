"""Download and install bundled FFmpeg for Moho Render Farm."""
import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

# FFmpeg essentials build from gyan.dev - static, smaller than full build (<100MB per exe)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
APP_ROOT = Path(__file__).parent.parent
FFMPEG_DIR = APP_ROOT / "ffmpeg"
FFMPEG_ZIP = APP_ROOT / "ffmpeg-download.zip"


def download_with_progress(url, dest):
    """Download a file with progress display, following redirects."""
    print(f"  Downloading from:\n  {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MohoRenderFarm/1.0"})
        response = urllib.request.urlopen(req)
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

    # Extract - public builds have nested directory structure:
    # ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
    print("  Extracting ffmpeg.zip...")
    try:
        FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(FFMPEG_ZIP), "r") as zf:
            # Find ffmpeg.exe and ffprobe.exe inside the zip
            extracted = []
            for member in zf.namelist():
                basename = os.path.basename(member)
                if basename in ("ffmpeg.exe", "ffprobe.exe"):
                    # Extract directly into FFMPEG_DIR (flatten the path)
                    target = FFMPEG_DIR / basename
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(basename)
                    print(f"  Extracted: {basename}")
    except (zipfile.BadZipFile, OSError) as e:
        print(f"  ERROR: Failed to extract: {e}")
        return False
    finally:
        # Clean up zip
        if FFMPEG_ZIP.exists():
            FFMPEG_ZIP.unlink()

    # Verify
    if (FFMPEG_DIR / "ffmpeg.exe").exists():
        print(f"  FFmpeg installed successfully ({len(extracted)} files)")
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
