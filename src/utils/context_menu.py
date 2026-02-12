"""Windows context menu (right-click) integration for Moho files."""
import sys
import os
import winreg
from pathlib import Path


APP_NAME = "MohoRenderFarm"
MENU_RENDER = "Render with Moho Render Farm"
MENU_ADD_QUEUE = "Add to Moho Render Farm Queue"


def get_app_path():
    """Get the path to the main application script."""
    return str(Path(__file__).parent.parent.parent / "main.py")


def get_python_path():
    """Get the Python executable path (windowless version)."""
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return sys.executable


def register_context_menu():
    """Register right-click context menu entries for .moho files."""
    python = get_python_path()
    app_path = get_app_path()
    extensions = [".moho", ".anime", ".anme"]

    for ext in extensions:
        try:
            # Create file type association
            key_path = f"Software\\Classes\\{ext}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"MohoProject{ext}")

            # Create type key
            type_key_path = f"Software\\Classes\\MohoProject{ext}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, type_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Moho Animation Project")

            # Shell - Render command
            shell_render = f"{type_key_path}\\shell\\MohoRenderFarm"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_render) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_RENDER)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f'"{python}"')

            cmd_render = f"{shell_render}\\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_render) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ,
                                  f'"{python}" "{app_path}" --render "%1"')

            # Shell - Add to queue command
            shell_queue = f"{type_key_path}\\shell\\MohoRenderFarmQueue"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_queue) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_ADD_QUEUE)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f'"{python}"')

            cmd_queue = f"{shell_queue}\\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_queue) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ,
                                  f'"{python}" "{app_path}" --add-to-queue "%1"')

        except OSError as e:
            print(f"Error registering context menu for {ext}: {e}")
            return False

    print("Context menu registered successfully for .moho, .anime, .anme files")
    return True


def unregister_context_menu():
    """Remove right-click context menu entries."""
    extensions = [".moho", ".anime", ".anme"]

    for ext in extensions:
        try:
            type_key_path = f"Software\\Classes\\MohoProject{ext}"
            _delete_key_recursive(winreg.HKEY_CURRENT_USER, type_key_path)
        except OSError:
            pass

    print("Context menu entries removed")
    return True


def _delete_key_recursive(root, path):
    """Recursively delete a registry key and all its subkeys."""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    subkey = winreg.EnumKey(key, 0)
                    _delete_key_recursive(root, f"{path}\\{subkey}")
                except OSError:
                    break
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def is_context_menu_registered():
    """Check if context menu is already registered."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            "Software\\Classes\\MohoProject.moho\\shell\\MohoRenderFarm"):
            return True
    except OSError:
        return False
