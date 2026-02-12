"""Windows shortcuts and startup integration."""
import os
import subprocess
import winreg
from pathlib import Path

APP_NAME = "Moho Render Farm"
APP_ROOT = Path(__file__).parent.parent.parent
START_BAT = str(APP_ROOT / "start.bat")
PYTHON_EXE = str(APP_ROOT / "python" / "pythonw.exe")
MAIN_PY = str(APP_ROOT / "main.py")

STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REG_NAME = "MohoRenderFarm"


def _create_shortcut(shortcut_path: str) -> bool:
    """Create a Windows .lnk shortcut using PowerShell."""
    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{PYTHON_EXE}"; '
        f'$s.Arguments = "main.py"; '
        f'$s.WorkingDirectory = "{APP_ROOT}"; '
        f'$s.Description = "{APP_NAME}"; '
        f'$s.Save()'
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _remove_shortcut(shortcut_path: str) -> bool:
    """Remove a shortcut file if it exists."""
    try:
        p = Path(shortcut_path)
        if p.exists():
            p.unlink()
        return True
    except Exception:
        return False


# --- Desktop ---

def _desktop_path() -> str:
    return str(Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop" / f"{APP_NAME}.lnk")


def has_desktop_shortcut() -> bool:
    return Path(_desktop_path()).exists()


def add_desktop_shortcut() -> bool:
    return _create_shortcut(_desktop_path())


def remove_desktop_shortcut() -> bool:
    return _remove_shortcut(_desktop_path())


# --- Start Menu ---

def _start_menu_path() -> str:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    folder = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return str(folder / f"{APP_NAME}.lnk")


def has_start_menu_shortcut() -> bool:
    return Path(_start_menu_path()).exists()


def add_start_menu_shortcut() -> bool:
    return _create_shortcut(_start_menu_path())


def remove_start_menu_shortcut() -> bool:
    return _remove_shortcut(_start_menu_path())


# --- Taskbar Pin ---

def _taskbar_pins_path() -> str:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    folder = Path(appdata) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar"
    return str(folder / f"{APP_NAME}.lnk")


def has_taskbar_shortcut() -> bool:
    return Path(_taskbar_pins_path()).exists()


def add_taskbar_shortcut() -> bool:
    """Add shortcut to taskbar pins folder."""
    return _create_shortcut(_taskbar_pins_path())


def remove_taskbar_shortcut() -> bool:
    return _remove_shortcut(_taskbar_pins_path())


# --- Startup (Run on Windows boot) ---

def has_startup_entry() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, STARTUP_REG_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def add_startup_entry() -> bool:
    """Add app to Windows startup via registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, STARTUP_REG_NAME, 0, winreg.REG_SZ,
                          f'"{PYTHON_EXE}" "{MAIN_PY}"')
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def remove_startup_entry() -> bool:
    """Remove app from Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, STARTUP_REG_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False
