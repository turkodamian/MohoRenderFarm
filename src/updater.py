"""Auto-update system for Moho Render Farm."""
import os
import re
import shutil
import tempfile
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Callable

GITHUB_RAW_CONFIG = "https://raw.githubusercontent.com/turkodamian/MohoRenderFarm/main/src/config.py"
GITHUB_ZIP_URL = "https://github.com/turkodamian/MohoRenderFarm/archive/refs/heads/main.zip"
APP_ROOT = Path(__file__).parent.parent

# Directories/files to skip when updating
SKIP_DIRS = {"python", "ffmpeg", "MohoProjects", "__pycache__", ".git", ".claude",
             "test_output", "output", "renders", "venv"}
SKIP_FILES = {".env", "nul", "prompt.txt"}


def _parse_version(version_str: str):
    """Parse version string like '1.3.2' into tuple (1, 3, 2)."""
    return tuple(int(x) for x in version_str.split("."))


def check_for_update(current_version: str) -> Optional[str]:
    """Check GitHub for a newer version.

    Returns the new version string if an update is available, or None.
    """
    try:
        req = urllib.request.Request(GITHUB_RAW_CONFIG,
                                     headers={"User-Agent": "MohoRenderFarm/1.0"})
        response = urllib.request.urlopen(req, timeout=10)
        content = response.read().decode("utf-8")

        match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content)
        if not match:
            return None

        remote_version = match.group(1)

        if _parse_version(remote_version) > _parse_version(current_version):
            return remote_version

    except Exception:
        pass

    return None


def download_and_install_update(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Download the latest version from GitHub and install it.

    Overwrites app files but preserves user data (python/, ffmpeg/, etc.).
    Returns True on success.
    """
    if on_progress:
        on_progress("Downloading update...")

    tmp_dir = tempfile.mkdtemp(prefix="moho_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")

    try:
        # Download zip
        req = urllib.request.Request(GITHUB_ZIP_URL,
                                     headers={"User-Agent": "MohoRenderFarm/1.0"})
        response = urllib.request.urlopen(req, timeout=60)

        with open(zip_path, "wb") as f:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                f.write(chunk)

        if on_progress:
            on_progress("Extracting update...")

        # Extract zip
        extract_dir = os.path.join(tmp_dir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # Find the root directory inside the zip (e.g., MohoRenderFarm-main/)
        extracted_items = os.listdir(extract_dir)
        if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
            source_dir = os.path.join(extract_dir, extracted_items[0])
        else:
            source_dir = extract_dir

        if on_progress:
            on_progress("Installing update...")

        # Copy files, skipping protected directories
        for item in os.listdir(source_dir):
            src = os.path.join(source_dir, item)
            dst = os.path.join(str(APP_ROOT), item)

            if item in SKIP_DIRS or item in SKIP_FILES:
                continue

            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        if on_progress:
            on_progress("Update installed successfully!")

        return True

    except Exception as e:
        if on_progress:
            on_progress(f"Update failed: {e}")
        return False

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass
