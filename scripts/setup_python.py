"""Download and install portable Python for Moho Render Farm."""
import os
import sys
import zipfile
import urllib.request
import shutil
import subprocess
from pathlib import Path

PYTHON_VERSION = "3.10.11"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
APP_ROOT = Path(__file__).parent.parent
PYTHON_DIR = APP_ROOT / "python"
PYTHON_ZIP = APP_ROOT / "python-download.zip"
PTH_FILE = PYTHON_DIR / "python310._pth"
REQUIREMENTS = APP_ROOT / "requirements.txt"


def download_with_progress(url, dest):
    """Download a file with progress display."""
    print(f"  Downloading from:\n  {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MohoRenderFarm/1.0"})
        response = urllib.request.urlopen(req)
    except urllib.error.URLError as e:
        print(f"  ERROR: Could not connect: {e}")
        return False

    total = int(response.headers.get("Content-Length", 0))
    downloaded = 0
    block_size = 1024 * 64

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


def setup_python():
    """Download and set up portable Python."""
    python_exe = PYTHON_DIR / "python.exe"

    if python_exe.exists():
        print("  Portable Python already installed. Skipping download.")
        return True

    # Download Python embeddable package
    print(f"  Downloading Python {PYTHON_VERSION} embeddable package...")
    if not download_with_progress(PYTHON_URL, str(PYTHON_ZIP)):
        return False

    # Extract
    print("  Extracting Python...")
    try:
        PYTHON_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(PYTHON_ZIP), "r") as zf:
            zf.extractall(str(PYTHON_DIR))
    except (zipfile.BadZipFile, OSError) as e:
        print(f"  ERROR: Failed to extract: {e}")
        return False
    finally:
        if PYTHON_ZIP.exists():
            PYTHON_ZIP.unlink()

    if not python_exe.exists():
        print("  ERROR: python.exe not found after extraction.")
        return False

    # Enable site-packages by modifying the ._pth file
    print("  Configuring Python paths...")
    if PTH_FILE.exists():
        content = PTH_FILE.read_text(encoding="utf-8")
        # Uncomment 'import site' line
        content = content.replace("#import site", "import site")
        PTH_FILE.write_text(content, encoding="utf-8")

    # Install pip
    print("  Installing pip...")
    getpip_path = PYTHON_DIR / "get-pip.py"
    if not download_with_progress(GETPIP_URL, str(getpip_path)):
        print("  WARNING: Could not download get-pip.py")
        return False

    result = subprocess.run(
        [str(python_exe), str(getpip_path), "--no-warn-script-location"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: pip installation failed:\n{result.stderr}")
        return False

    # Clean up get-pip.py
    if getpip_path.exists():
        getpip_path.unlink()

    # Install dependencies
    if REQUIREMENTS.exists():
        print("  Installing dependencies...")
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS),
             "--no-warn-script-location"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: Some dependencies failed to install:\n{result.stderr}")
        else:
            print("  Dependencies installed successfully.")

    print(f"  Portable Python {PYTHON_VERSION} installed successfully!")
    return True


if __name__ == "__main__":
    print("=" * 44)
    print("  Moho Render Farm - Python Setup")
    print("=" * 44)
    print()
    success = setup_python()
    sys.exit(0 if success else 1)
