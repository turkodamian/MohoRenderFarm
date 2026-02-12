"""Auto-update system for Moho Render Farm."""
import os
import re
import shutil
import subprocess
import sys
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
             "test_output", "output", "renders", "venv", "_update_staging"}
SKIP_FILES = {".env", "nul", "prompt.txt", "_apply_update.bat"}

STAGING_DIR = APP_ROOT / "_update_staging"
UPDATE_SCRIPT = APP_ROOT / "_apply_update.bat"


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


def download_and_stage_update(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Download the latest version and stage it for install on restart.

    Downloads the zip, extracts it to a staging directory, and writes a
    batch script that will copy the files after the app exits.
    Returns True if staging succeeded.
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
            on_progress("Staging update...")

        # Clean previous staging if any
        if STAGING_DIR.exists():
            shutil.rmtree(STAGING_DIR)
        STAGING_DIR.mkdir(parents=True)

        # Copy update files to staging, skipping protected directories
        for item in os.listdir(source_dir):
            src = os.path.join(source_dir, item)
            dst = os.path.join(str(STAGING_DIR), item)

            if item in SKIP_DIRS or item in SKIP_FILES:
                continue

            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # Write the batch script that applies the update after app exits
        _write_update_script()

        if on_progress:
            on_progress("Update downloaded — restart to apply")

        return True

    except Exception as e:
        if on_progress:
            on_progress(f"Update failed: {e}")
        # Clean up staging on failure
        try:
            if STAGING_DIR.exists():
                shutil.rmtree(STAGING_DIR)
        except Exception:
            pass
        return False

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


def _write_update_script():
    """Write a batch script that copies staged files to app root after exit."""
    app_root = str(APP_ROOT)
    staging = str(STAGING_DIR)
    python_exe = str(APP_ROOT / "python" / "pythonw.exe")
    main_py = str(APP_ROOT / "main.py")

    # Build list of skip dirs for the batch script
    skip_dirs_str = " ".join(f'"{d}"' for d in SKIP_DIRS)

    script = f'''@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Wait for the app to close (up to 30 seconds)
set WAITED=0
:wait_loop
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /i "pythonw.exe" >nul
if not errorlevel 1 (
    if !WAITED! lss 30 (
        timeout /t 1 /nobreak >nul
        set /a WAITED+=1
        goto wait_loop
    )
)

:: Also wait for python.exe
set WAITED=0
:wait_loop2
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /i "python.exe" >nul
if not errorlevel 1 (
    if !WAITED! lss 10 (
        timeout /t 1 /nobreak >nul
        set /a WAITED+=1
        goto wait_loop2
    )
)

:: Small extra delay to ensure file handles are released
timeout /t 2 /nobreak >nul

:: Copy staged files to app root
xcopy "{staging}\\*" "{app_root}\\" /E /Y /I /Q >nul 2>&1

:: Clean up staging directory
rmdir /S /Q "{staging}" >nul 2>&1

:: Relaunch the app
start "" "{python_exe}" "{main_py}"

:: Delete this script
del "%~f0"
'''
    with open(str(UPDATE_SCRIPT), "w", encoding="utf-8") as f:
        f.write(script)


def apply_staged_update():
    """Launch the update batch script and signal the app should exit.

    Returns True if the script was launched.
    """
    if not UPDATE_SCRIPT.exists() or not STAGING_DIR.exists():
        return False

    try:
        # Launch the batch script detached from this process
        subprocess.Popen(
            ["cmd.exe", "/c", str(UPDATE_SCRIPT)],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        return True
    except Exception:
        return False


def has_staged_update() -> bool:
    """Check if there's a staged update waiting to be applied."""
    return STAGING_DIR.exists() and UPDATE_SCRIPT.exists()


def clean_staged_update():
    """Remove staged update files if they exist."""
    try:
        if STAGING_DIR.exists():
            shutil.rmtree(STAGING_DIR)
    except Exception:
        pass
    try:
        if UPDATE_SCRIPT.exists():
            UPDATE_SCRIPT.unlink()
    except Exception:
        pass
